# Changelog
## Version 1.0.1
- Added `--no-cache` and `--no-environ`
- Added `BUILD_DIR` and `OUTPUT_DIR` variables
- Added environment variables to the variables if `--no-cache` is not set
- Added more things todo in `README.md`
- Added the clean commands in `README.md`

## Version 1.0.2
- Added compiler caching
- Added C(XX)/ASM flags
- Split `LINKER` into `STATIC` and `SHARED`
- Print error msgs in `sys.stderr`
  
## Version 1.0.3
- Did a tiny bit of optimization in the `compile()` function
- Added `--clean`
- Added `replace$`
- Added more conditions in if statements and changed variable definition check to `set()` in if statements
- Added `exit`

## Version 1.0.4
- Added `CONTRIBUTING.md`
- Added error code to `exit`
- Added nested functions
- Made the if conditions helper functions and added a `$` suffix
- Fixed files with compile errors being saved to the `.hashes` file

## Version 1.0.5
- Touched up the `Speed` section of the README.md
- Made `print` and `exit` functions instead of statements
- Added `exec` for subdirectories
- Skipped execution for empty lines and comments (lines starting with `;`)