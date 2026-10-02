cmake_minimum_required(VERSION 3.8)

project(CS-103-Autumn)

enable_testing()

set(CMAKE_CXX_STANDARD             20)
set(CMAKE_C_STANDARD             11)
set(CMAKE_MODULE_PATH              "${CMAKE_SOURCE_DIR}/cmake")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
set(CMAKE_EXPORT_COMPILE_COMMANDS  ON)

include_directories(contrib/catch)

include(Cmake/TestSolution.cmake)
include(Cmake/BuildFlags.cmake)

add_subdirectory(tasks)
add_subdirectory(examples)
include(Cmake/FindCatch.cmake)
add_catch(test_task_check tests/support/test_task_check.cpp)
add_test(NAME infrastructure_capture COMMAND test_task_check "[positive]")
set_tests_properties(infrastructure_capture PROPERTIES TIMEOUT 20)
foreach(check empty wrong exit timeout exception nan)
  add_test(NAME infrastructure_reject_${check} COMMAND test_task_check "[reject_${check}]")
  set_tests_properties(infrastructure_reject_${check} PROPERTIES WILL_FAIL TRUE TIMEOUT 15)
endforeach()
