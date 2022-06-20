cmake_minimum_required(VERSION 3.4)
project(oppai)

add_subdirectory(pybind11)
add_compile_options(-fpermissive)
pybind11_add_module(oppai SHARED bindings.cpp oppai.c)
