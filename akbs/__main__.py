#!/usr/bin/env python3
import os
import re
import sys
import glob
import subprocess
import json
import argparse

__version__ = "1.0.4"
__author__ = "Aarav Malani"
__license__ = "MIT"

commands = {
    "wildcard$": lambda ags: " ".join([" ".join(glob.glob(x, recursive=True)) for x in ags]),
    "remove$": lambda ags: " ".join([x for x in ags[0].split(" ") if x not in ags[1:]]),
    "replace$": lambda ags: ags[0].replace(ags[1], ags[2]),
    "eq$": lambda ags: ags[0] == ags[1],
    "neq$": lambda ags: ags[0] != ags[1],
    "gt$": lambda ags: float(ags[0]) > float(ags[1]),
    "lt$": lambda ags: float(ags[0]) < float(ags[1]),
    "gte$": lambda ags: float(ags[0]) >= float(ags[1]),
    "lte$": lambda ags: float(ags[0]) <= float(ags[1]),
    "set$": lambda ags: ags[0] in variables,
    "notset$": lambda ags: ags[0] not in variables,
    "and$": lambda ags: all(map(lambda x: x.lower() in ['true', 'on'], ags)),
    "or$": lambda ags: any(map(lambda x: x.lower() in ['true', 'on'], ags)),
    "not$": lambda ags: not ags[0].lower() in ['true', 'on']
}
language_to_compiler = {
    'C': ['cc', 'gcc', 'clang'],
    'CXX': ['c++', 'g++', 'clang++'],
    'ASM_INTEL': ['nasm', 'yasm', 'masm'],
    'ASM_ATT': ['as', 'gas'],
    'SHARED': ['gcc', 'clang', 'ld'],
    'STATIC': ['ar'],
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="akbs",
        description='A build system for C/C++/ASM')
    parser.add_argument('--file', '-f', help='the file to build from', default=["build.akbs"])
    parser.add_argument('--no-environ', '-e', action='store_true',
                        help='do not use environment variables')
    parser.add_argument('--no-cache', '-c', action='store_true',
                        help='do not use cache')
    parser.add_argument('--clean', '-C', action='store_true',
                        help='clean all build and cache files')
    parser.add_argument('--version', '-v', action='store_true', help='print version and exit')
    
    

    # Windows is unsupported right now
    if os.name == 'nt':
        print("Not supported in Windows (yet)", file=sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    if args.version:
        print("akbs "+__version__)
        print("Author: "+__author__)
        print("License: "+__license__)
        sys.exit(0)
    # Load old file modification times
    if os.path.exists('.hashes') and not args.no_cache:
        with open('.hashes', 'r') as f:
            hash_table = json.load(f)
    else:
        hash_table = {}

    # Called when an error occurs
    def error(d):

        if not args.no_cache:
            with open('.hashes', 'w') as f:
                json.dump(hash_table, f)
        print(d, file=sys.stderr)
        print("On line "+str(i), file=sys.stderr)
        print(lines[i], file=sys.stderr)
        sys.exit(1)

    # Load the build file
    if os.path.exists(args.file[0]):
        with open(args.file[0], 'r') as f:
            file = f.read()
    else:
        # Load from stdin
        if args.file[0] == '-':
            file = sys.stdin.read()
        else:
            print("File not found: "+args.file[0], file=sys.stderr)
            sys.exit(1)

    # Variable dict
    variables = {
        "PLATFORM": os.name.upper()
    }

    # Load compiler locations if they exist
    if os.path.exists('.comp_caches') and not args.no_cache:
        with open('.comp_caches', 'r') as f:
            comp_caches = json.load(f)
            variables.update(comp_caches)
    else:
        comp_caches = {}

    # Load environment variables
    if not args.no_environ:
        variables.update(os.environ)

    # Preprocessor defines
    defines = {}

    # Test code for a language
    code = {
        "C": "int main() {}",
        "CXX": "int main() {}",
        "ASM_INTEL": "global _start\n_start:\nret",
        "ASM_ATT": ".globl _start\n_start:\nret"
    }

    # Load the lines
    lines = file.split("\n")
    i = 0

    # Find the compiler/assembler/linker
    def look_for(to_check, val, use_cached=True):
        with open(os.devnull, 'w') as devnull:
            # Load cached compiler
            if use_cached and val+'_COMPILER' in variables:
                print("Checking for " +
                      variables[val+'_COMPILER']+"... found (cached)")
                return

            # Check for compiler
            for i in to_check:
                print("Checking for "+i+"...", end=" ")
                try:
                    # This call will fail if the compiler is not found and throw the error
                    subprocess.check_call(
                        i+' --version', stdout=devnull, stderr=devnull, shell=True)
                    print("found")
                    # Set the compiler
                    variables[val+'_COMPILER'] = i

                    # Check for standard
                    if val+'_STD' in variables:

                        print("Checking for "+i+" with "+val +
                              variables[val+'_STD']+"...", end=" ")
                        try:
                            # We actually need to compile code to check if the standard is supported
                            with open('.tmp.'+val.lower(), 'w') as f:
                                f.write(code[val])
                            # compiler -std=c/c++number .tmp.c/c++
                            subprocess.check_call(i+' -std='+val.lower().replace(
                                'x', '+')+variables[val+'_STD']+' .tmp.'+val.lower(), stdout=devnull, stderr=devnull, shell=True)
                            print("ok")
                            variables[val+'_COMPILER'] = i
                            return
                        except subprocess.CalledProcessError:
                            print("not ok")
                    else:
                        return
                except subprocess.CalledProcessError:
                    print("not found")

        error("Could not find any of "+", ".join(to_check))

    def clrdefines(data):
        # Find all preprocessor defines
        there = [(i, defines[i]) for i in defines if i in data]
        # Keep replacing until there are no more
        while there:
            # Replace the define with its value
            data = data.replace(*there.pop())
        return data

    def clrfuncs(data):
        def handle_command(match):
            # Get function name and arguments
            name, ags = match.groups()
            # Check if it is a helper command
            if not name.endswith('$'):
                return data[match.start():match.end()]
            # Strip whitespace and split into list of arguments
            ags = [i.strip() for i in ags.split(",")]
            # Get function and call it
            return str(commands.get(name, lambda ags: error("Command not found: "+name))(ags))
        # Keep replacing until substituting no longer changes the string
        old = ''
        while old != data:
            old = data
            # name(args) -> capturing group 1 is name, capturing group 2 is args
            # replace innermost function calls with their return value
            data = re.sub(r"([a-zA-Z\$]+)\(([^()]+)\)", handle_command, data)

        return data

    def clrvars(data):
        # Find all variables
        there = [('$'+i, variables[i]) for i in variables if "$"+i in data]
        # Keep replacing until there are no more
        while there:
            # Replace the variable with its value
            data = data.replace(*there.pop())
        return data

    while i < len(lines):
        # Preprocess the file and evaluate variables and helper functions
        lines[i] = clrfuncs(clrvars(clrdefines(lines[i]))).strip()
        # Preprocesser define
        if lines[i].startswith("%define"):
            # Split by a space a maximum of 2 times
            # (%define, name, value)
            st, to, vl = lines[i].split(" ", 2)
            defines[to] = vl
        # Set a variable
        elif lines[i].startswith("set"):
            # Get the arguments, split by a comma, strip whitespace, and remove empty strings
            k, v = [z.strip() for z in re.search(r"set[ ]*\((.+?)\)",
                                                 lines[i]).groups()[0].split(',') if z]
            # Remaining arguments should be the key, value

            # Set the variable
            variables[k] = v
        # If statement
        elif lines[i].startswith("if"):
            # Get the condition
            cond = re.search(r"if[ ]*\((.+)\)", lines[i]
                             ).groups()[0].replace(" ", "")
            # If the condition is false, skip to the next endif
            if not cond.lower() in ["true", "on"]:
                # Counter counts the depth of nested ifs
                c = 0
                i += 1
                while clrdefines(lines[i]) not in ["endif"] or c:
                    # Add to the counter if there is another if
                    if clrdefines(lines[i]).startswith('if'):
                        c += 1
                    # Subtract from the counter if there is an endif
                    elif clrdefines(lines[i]).startswith(('endif',)):
                        c -= 1
                    i += 1
        # Check for a compiler/assembler/linker
        elif lines[i].startswith("check_for"):
            # Skip this if we are cleaning
            if args.clean:
                i += 1
                continue
            # Get the arguments, split by a comma, strip whitespace, and remove empty strings
            to_check = [i.strip() for i in re.search(
                r"check_for[ ]*\((.+?)\)", lines[i]).groups()[0].replace(" ", "").split(",")]
            # Remaining arguments should be the languages to check

            for x in to_check:
                # Call look_for with the compiler / assembler / linker
                look_for(language_to_compiler[x], x)
        
        # Print a message
        elif lines[i].startswith("print"):
            # TODO: make this a function not a statement
            print(" ".join(lines[i].split(" ")[1:]))
        
        # Compile a list of files and link them in one go
        elif lines[i].startswith("compile"):
            # Get the list of files and the library file type
            what, files = [i.strip() for i in re.search( 
                r"compile[ ]*\((.+?)\)", lines[i]).groups()[0].split(",")]
            
            # Convert the list of files into a list of object files
            objs = [variables.get("BUILD_DIR", ".") + "/" + (".".join(x.split(".")[:-1] + ['o'])) for x in files.split(' ')
                    if x.split('.')[-1] in ['c', 'cpp', 'asm', 'S']]
            
            # If we are cleaning, remove the object files and the library
            if args.clean:
                for obj in objs:
                    if os.path.exists(obj):
                        os.remove(obj)
                if os.path.exists(variables.get("OUTPUT_DIR", ".") + "/" + variables.get("OUTPUT")):
                    os.remove(variables.get("OUTPUT_DIR", ".") +
                              "/" + variables.get("OUTPUT"))
                i += 1
                continue

            # Get the list of files and iterate over them
            for file in files.split(' '):
                # Check if the file is already compiled
                if not args.no_cache:
                    if file in hash_table:
                        # Get the modification time and see if it is the same as the one we have saved
                        if hash_table[file] == os.path.getmtime(file) and os.path.exists(variables.get("BUILD_DIR", ".") + "/" + (".".join(file.split('.')[:-1])+'.o')):
                            continue
                    

                # Make the directory if it doesn't exist
                if 'BUILD_DIR' in variables:
                    os.makedirs(variables['BUILD_DIR'] +
                                '/'+os.path.dirname(file), exist_ok=True)

                # Get the language
                language = {'c': 'C', 'cpp': 'CXX',
                            'asm': 'ASM_INTEL', 'S': 'ASM_ATT'}[file.split('.')[-1]]

                def exec():
                    # Compile the file
                    # compiler -o BUILD_DIR/file.o (-c or -felf64) file -std=language_STD (language_FLAGS)
                    cmd = variables[language+'_COMPILER'] + ' -o '+variables.get("BUILD_DIR", ".")+"/"+(".".join(file.split('.')[:-1]))+'.o ' + ('-felf64 ' if file.split('.')[-1] in ['asm', 'S'] else '-c ') + file + (
                        (' -std='+{'c': 'c', 'cpp': 'c++'}[file.split('.')[-1]]+variables[str({'c': 'C', 'cpp': 'CXX'}.get(file.split('.')[-1], None))+'_STD']) if str({'c': 'C', 'cpp': 'CXX'}.get(file.split('.')[-1], None))+'_STD' in variables else '' + (variables.get(language+'_FLAGS', '')))
                    print(cmd)
                    return os.system(cmd)
                return_code = exec()
                # 0x7F00 is the error code for "command not found" (127 << 8)
                # If the compiler is cached, and we can't find it, configure it again
                if return_code == 0x7F00 and language+'_COMPILER' in comp_caches:
                    look_for(language_to_compiler[language], language, False)
                    return_code = exec()

                # Check for errors
                if return_code != 0:
                    error("Compilation failed")
                if not args.no_cache:
                    # Update the modification time
                    hash_table[file] = os.path.getmtime(file)
            
            #Create the output directory if it doesn't exist
            os.makedirs(os.path.dirname(variables.get(
                'OUTPUT_DIR', '.')+'/'+variables['OUTPUT']), exist_ok=True)
            
            # Link the files
            # linker (-o or nothing (for ar)) OUTPUT_DIR/OUTPUT (-shared or rcs) objs
            print(" ".join([variables[what.upper()+'_COMPILER'], ('-shared' if what.upper() == 'SHARED' else 'rcs'), ('-o' if what.upper() == 'SHARED' else ''),
                            variables.get('OUTPUT_DIR', '.')+'/'+variables['OUTPUT'], ' '.join(objs)]))
            os.system(" ".join([variables[what.upper()+'_COMPILER'], ('-shared' if what.upper() == 'SHARED' else 'rcs'), ('-o' if what.upper() == 'SHARED' else ''),
                      variables.get('OUTPUT_DIR', '.')+'/'+variables['OUTPUT'], ' '.join(objs)]))
            
        # Exit the program
        elif lines[i].startswith('exit'):
            # TODO: Make this a function not a statement
            # Check for an exit code
            arguments = [x.strip() for x in lines[i].split(" ") if x]
            # Exit with 0 or the exit code
            sys.exit(int(arguments[1]) if len(arguments) > 1 else 0)
        i += 1
    # Remove the cache files if we are cleaning
    if args.clean:
        os.remove('.hashes')
        os.remove('.comp_caches')
        sys.exit(0)
    # Save the cache files 
    if not args.no_cache:
        with open('.hashes', 'w') as f:
            json.dump(hash_table, f)
        with open('.comp_caches', 'w') as f:
            json.dump({
                val+'_COMPILER': variables.get(val+'_COMPILER') for val in language_to_compiler if val+'_COMPILER' in variables and variables[val+'_COMPILER']
            }, f)
