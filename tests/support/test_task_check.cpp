#include "task_check.h"

namespace {
int EchoInput() {
    char buffer[128];
    while (std::fgets(buffer, sizeof(buffer), stdin) != nullptr) {
        std::fputs(buffer, stdout);
    }
    return 0;
}
int ReadFile() {
    std::ifstream input("input.txt");
    std::string word;
    input >> word;
    std::cout << word;
    return 0;
}
int Empty() { return 0; }
int Wrong() { std::puts("999"); return 0; }
int Error() { std::puts("1"); return 256; }
int Hangs() { for (;;) { pause(); } }
int Throws() { throw std::runtime_error("failure"); }
}  // namespace

TEST_CASE("stdin and output capture", "[positive]") {
    course_test::CheckTask(EchoInput, "1 2\n3", "1\n2 3");
}
TEST_CASE("file and C++ output capture", "[positive]") {
    course_test::CheckTask(ReadFile, "hello", "hello");
}
TEST_CASE("exact and numeric comparisons", "[positive]") {
    course_test::CheckTask(EchoInput, "a\nb", "a\nb", 0, true);
    course_test::CheckTask(EchoInput, "1.00000001", "1", 1e-6);
}
TEST_CASE("reject empty solution", "[reject_empty]") {
    course_test::CheckTask(Empty, "", "1");
}
TEST_CASE("reject wrong answer", "[reject_wrong]") {
    course_test::CheckTask(Wrong, "", "1");
}
TEST_CASE("reject nonzero exit", "[reject_exit]") {
    course_test::CheckTask(Error, "", "1");
}
TEST_CASE("reject timeout", "[reject_timeout]") {
    course_test::CheckTask(Hangs, "", "1");
}
TEST_CASE("reject exception", "[reject_exception]") {
    course_test::CheckTask(Throws, "", "1");
}
TEST_CASE("reject NaN", "[reject_nan]") {
    course_test::CheckTask(EchoInput, "nan", "1", 1e-6);
}
