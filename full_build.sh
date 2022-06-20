find . -name "*.c" -type f -delete
find . -name "*.o" -type f -delete
find . -name "*.so" -type f -delete
python3.9 setup.py build_ext --inplace
date +%s > build.date
