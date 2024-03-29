from conans import ConanFile, CMake, tools
import os
import sys


class DefaultNameConan(ConanFile):
    settings = "os", "compiler", "arch", "build_type"
    generators = "cmake"

    def with_complex(self):
        return not self.options["boost"].without_filesystem and not self.options["boost"].without_log and not self.options["boost"].without_fiber

    def build(self):
        cmake = CMake(self)
        if self.options["boost"].header_only:
            cmake.definitions["HEADER_ONLY"] = "TRUE"
        if not self.options["boost"].without_python:
            cmake.definitions["WITH_PYTHON"] = "TRUE"
        if not self.options["boost"].without_random:
            cmake.definitions["WITH_RANDOM"] = "TRUE"
        if not self.options["boost"].without_regex:
            cmake.definitions["WITH_REGEX"] = "TRUE"
        if not self.options["boost"].without_test:
            cmake.definitions["WITH_TEST"] = "TRUE"
        if not self.options["boost"].without_coroutine:
            cmake.definitions["WITH_COROUTINE"] = "TRUE"
        if not self.options["boost"].without_chrono:
            cmake.definitions["WITH_CHRONO"] = "TRUE"
        if self.with_complex():
            cmake.definitions["WITH_COMPLEX"] = "TRUE"

        cmake.configure()
        cmake.build()

    def test(self):
        if self.settings.os == 'Emscripten':
            self.run('node %s' % os.path.join("bin", "lambda_exe.js 1 2 3"), run_environment=True)

        if tools.cross_building(self.settings):
            return

        self.run(os.path.join("bin", "lambda_exe 1 2 3"), run_environment=True)
        if self.options["boost"].header_only:
            return

        if not self.options["boost"].without_random:
            self.run(os.path.join("bin", "random_exe"), run_environment=True)
        if not self.options["boost"].without_regex:
            self.run(os.path.join("bin", "regex_exe"), run_environment=True)
        if not self.options["boost"].without_test:
            self.run(os.path.join("bin", "test_exe"), run_environment=True)
        if not self.options["boost"].without_coroutine:
            self.run(os.path.join("bin", "coroutine_exe"), run_environment=True)
        if not self.options["boost"].without_chrono:
            self.run(os.path.join("bin", "chrono_exe"), run_environment=True)
        if self.with_complex():
            self.run(os.path.join("bin", "complex_exe"), run_environment=True)
        if not self.options["boost"].without_python:
            os.chdir("bin")
            sys.path.append(".")
            import hello_ext
            hello_ext.greet()
