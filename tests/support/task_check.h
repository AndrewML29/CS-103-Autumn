#pragma once

#include <catch.hpp>

#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <stdexcept>
#include <iostream>
#include <vector>
#include <sys/wait.h>
#include <unistd.h>

// Each fixture runs in a separate process and working directory.
// No task implementations or reference algorithms belong in this file.
namespace course_test {
struct Workspace {
    std::string path;
    Workspace() {
        char name[] = "/tmp/cs103-case-XXXXXX";
        char* created = mkdtemp(name);
        if (created == nullptr) {
            throw std::runtime_error("Cannot create test workspace");
        }
        path = created;
    }
    ~Workspace() {
        std::error_code ignored;
        std::filesystem::remove_all(path, ignored);
    }
};

inline std::vector<std::string> Tokens(const std::string& text) {
    std::istringstream stream(text);
    std::vector<std::string> tokens;
    for (std::string token; stream >> token;) {
        tokens.push_back(token);
    }
    return tokens;
}

inline bool EqualNumber(const std::string& actual, const std::string& expected,
                        double tolerance) {
    char* end_actual = nullptr;
    char* end_expected = nullptr;
    const double a = std::strtod(actual.c_str(), &end_actual);
    const double e = std::strtod(expected.c_str(), &end_expected);
    return end_actual != actual.c_str() && *end_actual == '\0' &&
           end_expected != expected.c_str() && *end_expected == '\0' &&
           std::isfinite(a) && std::isfinite(e) &&
           std::fabs(a - e) <= tolerance * std::fmax(1.0, std::fabs(e));
}

inline void CheckTask(int (*task)(), const std::string& input,
                      const std::string& expected, double tolerance = 0, bool exact = false) {
    Workspace workspace;
    const std::string input_path = workspace.path + "/input.txt";
    const std::string output_path = workspace.path + "/output.txt";
    {
        std::ofstream file(input_path);
        REQUIRE(file.good());
        file << input;
    }
    std::fflush(nullptr);
    const pid_t child = fork();
    REQUIRE(child >= 0);
    if (child == 0) {
        if (chdir(workspace.path.c_str()) != 0 ||
            freopen("input.txt", "r", stdin) == nullptr ||
            freopen("output.txt", "w", stdout) == nullptr) {
            _exit(120);
        }
        alarm(3);
        try {
            const int result = task();
            std::cout.flush();
            std::fflush(nullptr);
            // Nonzero results must remain nonzero even outside the 8-bit range.
            _exit(result == 0 ? 0 : 1);
        } catch (...) {
            _exit(121);
        }
    }
    int status = 0;
    pid_t waited;
    do {
        waited = waitpid(child, &status, 0);
    } while (waited == -1 && errno == EINTR);
    REQUIRE(waited == child);
    INFO("Input: " << input);
    INFO("Child status: " << status << "; signal may indicate a timeout or memory error");
    REQUIRE(WIFEXITED(status));
    REQUIRE(WEXITSTATUS(status) == 0);
    std::ifstream file(output_path);
    REQUIRE(file.good());
    std::ostringstream contents;
    contents << file.rdbuf();
    INFO("Expected: " << expected);
    INFO("Actual: " << contents.str());
    if (exact) {
        CHECK(contents.str() == expected);
        return;
    }
    auto actual = Tokens(contents.str());
    auto wanted = Tokens(expected);
    REQUIRE(actual.size() == wanted.size());
    for (size_t i = 0; i < wanted.size(); ++i) {
        INFO("Token index: " << i);
        if (tolerance > 0) {
            CHECK(EqualNumber(actual[i], wanted[i], tolerance));
        } else {
            CHECK(actual[i] == wanted[i]);
        }
    }
}
}  // namespace course_test
