#!/usr/bin/env python3
import os
import re
import sys
import glob
import subprocess
import json
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='A build system for C/C++/ASM')
    parser.add_argument('--file', '-f', metavar='FILE', type=str, nargs=1,
                        help='the file to build from', default=["build.akbs"])
    parser.add_argument('--no-environ', '-e', action='store_true',
                        help='do not use environment variables')
    parser.add_argument('--no-cache', '-c', action='store_true',
                        help='do not use cache')
    if os.name == 'nt':
        print("Not supported in Windows (yet)", file=sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    if os.path.exists('.hashes') and not args.no_cache:
        with open('.hashes', 'r') as f:
            hash_table = json.load(f)
    else:
        hash_table = {}

    

    def error(d):
        if not args.no_cache:
            with open('.hashes', 'w') as f:
                json.dump(hash_table, f)
        print(d, file=sys.stderr)
        print("On line "+str(i), file=sys.stderr)
        print(lines[i], file=sys.stderr)
        sys.exit(1)

    if os.path.exists(args.file[0]):
        with open(args.file[0], 'r') as f:
            file = f.read()
    else:
        if args.file[0] == '-':
            file = sys.stdin.read()
        else:
            print("File not found: "+args.file[0], file=sys.stderr)
            sys.exit(1)
    variables = {
        "PLATFORM": os.name.upper()
    }

    if os.path.exists('.comp_caches') and not args.no_cache:
        with open('.comp_caches', 'r') as f:
            comp_caches = json.load(f)
            variables.update(comp_caches)
    else:
        comp_caches = {}
    

    if not args.no_environ:
        variables.update(os.environ)
    

    defines = {}
    code = {
        "C": "int main() {}",
        "CXX": "int main() {}",
        "ASM_INTEL": "global _start\n_start:\nret",
        "ASM_ATT": ".globl _start\n_start:\nret"
    }

    lines = file.split("\n")
    i = 0

    def look_for(to_check, val, use_cached=True):
        with open(os.devnull, 'w') as devnull:
            if use_cached and val+'_COMPILER' in variables:
                print("Checking for "+variables[val+'_COMPILER']+"... found (cached)")
                return
                    
            for i in to_check:
                print("Checking for "+i+"...", end=" ")
                try:
                    subprocess.check_call(
                        i+' --version', stdout=devnull, stderr=devnull, shell=True)
                    print("found")
                    variables[val+'_COMPILER'] = i
                    if val+'_STD' in variables:
                        print("Checking for "+i+" with "+val +
                              variables[val+'_STD']+"...", end=" ")
                        try:
                            with open('.tmp.'+val.lower(), 'w') as f:
                                f.write(code[val])
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
            data = data.replace(*there.pop())
        return data

    def wildcard_handler(vs, chng, data):
        for zzz in vs:
            tmp = " ".join([" ".join([("\""+bruh+"\"" if " " in bruh else bruh) for bruh in glob.glob(
                xxz, recursive=True)]) for xxz in zzz.groups()[0].split(" ")])
            tmplist = list(data)
            tmplist[zzz.span()[0]+chng:zzz.span()
                    [1]+chng] = tmp
            data = "".join(tmplist)
            chng += len(tmp)-zzz.span()[1]+zzz.span()[0]
        return chng, data

    def remove_handler(vs, chng, data):
        for zzz in vs:
            args = [i.strip()
                    for i in zzz.groups()[0].split(",")]
            tmp = " ".join(
                [i for i in args[0].split(" ") if i not in args[1:]])
            tmplist = list(data)
            tmplist[zzz.span()[0]+chng:zzz.span()
                    [1]+chng] = tmp
            data = "".join(tmplist)
            chng += len(tmp)-zzz.span()[1]+zzz.span()[0]
        return chng, data
    def clrfuncs(data):
        for i in ["wildcard$", "remove$"]:
            chng = 0
            vs = list(re.finditer(
                i.replace("$", "\\$")+r"[ ]*\((.+?)\)", data))
            if vs:
                chng, data = {
                    "wildcard$": wildcard_handler,
                    "remove$": remove_handler,

                }.get(i, lambda _, no2, no3: error("Please report this error to the developer (https://github.com/AaravMalani/AKBS/issues/new)"))(vs, chng, data)
                
        return data

    def clrvars(data):
        there = [('$'+i, variables[i]) for i in variables if "$"+i in data]
        while there:
            data = data.replace(*there.pop())
        return data

    def eq_handler(cond):
        global i
        k, v = [i.strip() for i in re.search(r"eq[ ]*\((.+?)\)", cond).groups()
                [0].replace(" ", "").split(",")]
        if k != v:
            c = 0
            i += 1
            while clrdefines(lines[i]) not in ["endif"] or c:
                if clrdefines(lines[i]).startswith('if'):
                    c += 1
                elif clrdefines(lines[i]).startswith(('endif',)):
                    c -= 1
                i += 1
    while i < len(lines):
        lines[i] = clrfuncs(clrvars(clrdefines(lines[i])))
        if lines[i].startswith("%define"):
            st, to, vl = lines[i].split(" ", 2)
            defines[to] = vl
        elif lines[i].replace(" ", "").startswith("set("):
            k, v = [z.strip() for z in re.search(r"set[ ]*\((.+?)\)",
                                                 lines[i]).groups()[0].split(',') if z]
            variables[k] = v
        elif lines[i].startswith("if"):

            cond = re.search(r"if[ ]*\((.+)\)", lines[i]
                             ).groups()[0].replace(" ", "")
            if not cond.startswith(("eq",)) and cond not in variables:
                c = 0

                while clrdefines(lines[i]) not in ["endif"] or c:
                    if clrdefines(lines[i]).startswith('if'):
                        c += 1
                    i += 1
                    if clrdefines(lines[i]).startswith(('endif',)):
                        c -= 1
            else:
                {
                    "eq": eq_handler
                }.get(cond[:cond.index("(")], lambda x: error("Undefined condition "+cond[:cond.index("(")]))(cond)
        elif lines[i].startswith("check_for"):
            to_check = [i.strip() for i in re.search(
                r"check_for[ ]*\((.+?)\)", lines[i]).groups()[0].replace(" ", "").split(",")]
            for x in to_check:
                look_for({
                    'C': ['cc', 'gcc', 'clang'],
                    'CXX': ['c++', 'g++', 'clang++'],
                    'ASM_INTEL': ['nasm', 'yasm', 'masm'],
                    'ASM_ATT': ['as', 'gas'],
                    'SHARED': ['gcc', 'clang', 'ld'],
                    'STATIC': ['ar'],
                }[x], x)
        elif lines[i].startswith("print"):
            print(" ".join(lines[i].split(" ")[1:]))
        elif lines[i].startswith("compile"):
            what, files = [i.strip() for i in re.search(
                r"compile[ ]*\((.+?)\)", lines[i]).groups()[0].split(",")]
            objs = [variables.get("BUILD_DIR",".") + "/" + (".".join(x.split(".")[:-1] + ['o'])) for x in files.split(' ')
                    if x.split('.')[-1] in ['c', 'cpp', 'asm', 'S']]
            for x in files.split(' '):
                if not args.no_cache:
                    if x in hash_table:
                        if hash_table[x] == os.path.getmtime(x) and os.path.exists(variables.get("BUILD_DIR",".") + "/" + (".".join(x.split('.')[:-1])+'.o')):
                            continue
                    hash_table[x] = os.path.getmtime(x)
                if 'BUILD_DIR' in variables:
                    os.makedirs(variables['BUILD_DIR']+'/'+os.path.dirname(x),exist_ok=True)
                
                def exec():
                    cmd = variables[{'c': 'C', 'cpp': 'CXX', 'asm': 'ASM_INTEL', 'S': 'ASM_ATT'}[x.split('.')[-1]]+'_COMPILER'] + ' -o '+variables.get("BUILD_DIR",".")+"/"+(".".join(x.split('.')[:-1]))+'.o ' + ('-felf64 ' if x.split('.')[-1] in ['asm', 'S'] else '-c ') + x + (
                        (' -std='+{'c': 'c', 'cpp': 'c++'}[x.split('.')[-1]]+variables[str({'c': 'C', 'cpp': 'CXX'}.get(x.split('.')[-1], None))+'_STD']) if str({'c': 'C', 'cpp': 'CXX'}.get(x.split('.')[-1], None))+'_STD' in variables else '' + (variables.get({'c': 'C', 'cpp': 'CXX', 'asm': 'ASM_INTEL', 'S': 'ASM_ATT'}[x.split('.')[-1]]+'_FLAGS', '')))
                    print(cmd)
                    return os.system(cmd)
                val = exec()
                if val == 0x7F00 and {'c': 'C', 'cpp': 'CXX', 'asm': 'ASM_INTEL', 'S': 'ASM_ATT'}[x.split('.')[-1]]+'_COMPILER' in comp_caches:
                    look_for({
                        'c': ['cc', 'gcc', 'clang'],
                        'cpp': ['c++', 'g++', 'clang++'],
                        'asm': ['nasm', 'yasm', 'masm'],
                        'S': ['as', 'gas']
                    }[x.split('.')[-1]], {'c': 'C', 'cpp': 'CXX', 'asm': 'ASM_INTEL', 'S': 'ASM_ATT'}[x.split('.')[-1]], False)
                    val = exec()
                if val != 0:
                    error("Compilation failed")
            os.makedirs(os.path.dirname(variables.get('OUTPUT_DIR','.')+'/'+variables['OUTPUT']), exist_ok=True)
            print(" ".join([variables[what.upper()+'_COMPILER'], ('-shared' if what.upper() == 'SHARED' else 'rcs'), ('-o' if what.upper() == 'SHARED' else ''),
                      variables.get('OUTPUT_DIR','.')+'/'+variables['OUTPUT'],' '.join(objs)]))
            os.system(" ".join([variables[what.upper()+'_COMPILER'], ('-shared' if what.upper() == 'SHARED' else 'rcs'), ('-o' if what.upper() == 'SHARED' else ''),
                      variables.get('OUTPUT_DIR','.')+'/'+variables['OUTPUT'],' '.join(objs)]))
        elif lines[i] == 'endif':
            pass
        i += 1
    if not args.no_cache:
        with open('.hashes', 'w') as f:
            json.dump(hash_table, f)
        with open('.comp_caches', 'w') as f:
            json.dump({
                val+'_COMPILER': variables.get(val+'_COMPILER') for val in ['C', 'CXX', 'ASM_INTEL', 'ASM_ATT', 'STATIC', 'SHARED'] if val+'_COMPILER' in variables and variables[val+'_COMPILER']
            }, f)