from conans import ConanFile
from conans import tools
from conans.tools import Version, cppstd_flag

import os
import shutil

# NOTE: Adapted from the conan-center recipe
# https://github.com/conan-io/conan-center-index/tree/master/recipes/boost

# NOTE: Building under Windows requires MS Visual Studio and Windows SDK to be installed

VERBOSE_BUILD_LOG = False

# From from *1 (see below, b2 --show-libraries), also ordered following linkage order
# see https://github.com/Kitware/CMake/blob/master/Modules/FindBoost.cmake to know the order

LIB_LIST = ['math', 'wave', 'container', 'contract', 'exception', 'graph', 'iostreams', 'locale', 'log',
            'program_options', 'random', 'regex', 'mpi', 'serialization',
            'coroutine', 'fiber', 'context', 'timer', 'thread', 'chrono', 'date_time',
            'atomic', 'filesystem', 'system', 'graph_parallel', 'python',
            'stacktrace', 'test', 'type_erasure']


class BoostConan(ConanFile):
    name = 'boost'
    settings = 'os', 'arch', 'compiler', 'build_type'
    description = 'Boost provides free peer-reviewed portable C++ source libraries'
    license = 'Boost Software License - Version 1.0. http://www.boost.org/LICENSE_1_0.txt'
    python_requires = 'platform-inspector/0.0.1@conan-burrito/stable'

    # The current python option requires the package to be built locally, to find default Python
    # implementation
    options = {
        'shared': [True, False],
        'header_only': [True, False],
        'error_code_header_only': [True, False],
        'system_no_deprecated': [True, False],
        'asio_no_deprecated': [True, False],
        'filesystem_no_deprecated': [True, False],
        'fPIC': [True, False],
        'layout': ['system', 'versioned', 'tagged', 'b2-default'],
        'magic_autolink': [True, False],  # enables BOOST_ALL_NO_LIB
        'multithreading': [True, False],
        'segmented_stacks': [True, False],
        'debug_level': [i for i in range(0, 14)],
        'extra_b2_flags': 'ANY',
        'visibility': ['global', 'protected', 'hidden'],
    }
    options.update({"without_%s" % libname: [True, False] for libname in LIB_LIST})

    default_options = {
        'shared': False,
        'header_only': False,
        'error_code_header_only': False,
        'system_no_deprecated': False,
        'asio_no_deprecated': False,
        'filesystem_no_deprecated': False,
        'layout': 'system',
        'fPIC': True,
        'magic_autolink': False,
        'multithreading': True,
        'segmented_stacks': False,
        'debug_level': 0,
        'extra_b2_flags': 'None',
        'visibility': 'hidden',
    }

    for x in LIB_LIST:
        if x != 'python':
            default_options.update({'without_%s' % x: False})
    default_options.update({'without_python': True})

    # For PlatformInspector
    generators = 'cmake'

    short_paths = True
    no_copy_source = True
    exports_sources = ['patches/*']
    build_policy = 'missing'

    @property
    def boost_version(self):
        return str(self.version)

    @property
    def _source_subfolder(self):
        return 'src'

    @property
    def _boost_build_dir(self):
        return os.path.join(self.source_folder, self._source_subfolder, "tools", "build")

    @property
    def _is_msvc(self):
        return self.settings.compiler == "Visual Studio"

    @property
    def _is_clang_cl(self):
        return self.settings.os == "Windows" and self.settings.compiler == "clang"

    @property
    def _zip_bzip2_requires_needed(self):
        return not self.options.without_iostreams and not self.options.header_only

    @property
    def _cxx(self):
        if 'CXX' in os.environ:
            return os.environ['CXX']

        return self.platform_inspector.cxx

    @property
    def _ar(self):
        if 'AR' in os.environ:
            return os.environ['AR']

        return self.platform_inspector.ar

    @property
    def _ranlib(self):
        if 'RANLIB' in os.environ:
            return os.environ['RANLIB']

        return self.platform_inspector.ranlib

    def _get_named_flags(self, env_var, inspector_attr):
        env_flags = ''
        if env_var in os.environ:
            env_flags = os.environ[env_var]

        flags = getattr(self.platform_inspector, inspector_attr)
        flags.append(env_flags)

        result = ' '.join(flags)
        return result if len(result.strip()) != 0 else None

    @property
    def _c_flags(self):
        return self._get_named_flags('CFLAGS', 'c_flags')

    @property
    def _as_flags(self):
        return self._get_named_flags('ASFLAGS', 'asm_flags')

    @property
    def _cxx_flags(self):
        flags = self._get_named_flags('CXXFLAGS', 'cxx_flags')
        def append(flag):
            nonlocal flags
            if flags is not None:
                flags = flags + ' ' + flag
            else:
                flags = flag

        if str(self.settings.os) in ['watchOS', 'tvOS']:
            # 'sigaltstack' is unavailable: not available on tvOS / watchOS
            append('-DBOOST_TEST_DISABLE_ALT_STACK=1')

        if self.settings.get_safe("compiler.cppstd"):
            append(cppstd_flag(self.settings))

        return flags

    @property
    def _ld_flags(self):
        if self.options.shared:
            return self._get_named_flags('LDFLAGS', 'ld_shared_flags')
        else:
            return self._get_named_flags('LDFLAGS', 'ld_static_flags')

    @property
    def _b2_exe(self):
        folder = os.path.join(self.source_folder, self._source_subfolder, "tools", "build")
        return os.path.join(folder, "b2.exe" if tools.os_info.is_windows else "b2")

    @property
    def _boost_dir(self):
        # return self._bcp_dir if self._use_bcp else self._source_subfolder
        return self._source_subfolder

    @property
    def _toolset(self):
        compiler = str(self.settings.compiler)
        if self._is_msvc:
            return "msvc"
        elif self.settings.os == "Windows" and compiler == "clang":
            return "clang-win"
        elif self.settings.os == "Emscripten" and compiler == "clang":
            return "emscripten"
        elif compiler == "gcc" and tools.is_apple_os(self.settings.os):
            return "darwin"
        elif compiler == "apple-clang":
            return "clang-darwin"
        elif self.settings.os == "Android" and compiler == "clang":
            return "clang-linux"
        elif str(self.settings.compiler) in ["clang", "gcc"]:
            return compiler
        elif compiler == "sun-cc":
            return "sunpro"
        elif compiler == "intel":
            toolset = {"Macos": "intel-darwin",
                       "Windows": "intel-win",
                       "Linux": "intel-linux"}.get(str(self.settings.os))
            return toolset
        else:
            return compiler

    @property
    def _toolset_version(self):
        compiler_version = str(self.settings.compiler.version)
        compiler = str(self.settings.compiler)
        major = Version(compiler_version).major
        if self._is_msvc:
            if Version(compiler_version) >= "16":
                return "14.2"
            elif Version(compiler_version) >= "15":
                return "14.1"
            else:
                return "%s.0" % compiler_version
        elif compiler == "gcc" and tools.is_apple_os(self.settings.os):
            return compiler_version
        elif compiler == "gcc" and int(major) >= 5:
            return str(major)

        return compiler_version

    @property
    def _is_versioned_layout(self):
        layout = self.options.get_safe("layout")
        return layout == "versioned" or (layout == "b2-default" and os.name == 'nt')

    def requirements(self):
        if self._zip_bzip2_requires_needed:
            self.requires('bzip2/1.0.8@conan-burrito/stable')
            self.requires('zlib/1.2.11@conan-burrito/stable')

    def source(self):
        tools.get(**self.conan_data["sources"][self.version])
        os.rename("boost_%s" % self.version.replace(".", "_"), self._source_subfolder)
        for patch in self.conan_data["patches"].get(self.version, []):
            tools.patch(**patch)

    def build(self):
        if self.options.header_only:
            self.output.warn("Header only package, skipping build")
            return

        self.platform_inspector = self.python_requires['platform-inspector'].module.PlatformInspector(conanfile=self,
                                                                                                      verbose=True)

        self._clean()
        self._bootstrap()

        self._write_user_config_jam()

        b2_flags = ' '.join(self._build_flags)  # + ' --no-cmake-config'
        full_command = '%s %s' % (self._b2_exe, b2_flags)
        full_command += ' --debug-configuration --build-dir="%s"' % self.build_folder

        if VERBOSE_BUILD_LOG:
            full_command += ' -d2'

        self.output.warn(full_command)

        sources = os.path.join(self.source_folder, self._boost_dir)
        with tools.vcvars(self.settings) if self._is_msvc else tools.no_op():
            with tools.chdir(sources):
                # To show the libraries *1
                # self.run("%s --show-libraries" % b2_exe)
                self.run(full_command, run_environment=True)


    # ---------- BUILDING METHODS ----------

    def _clean(self):
        src = os.path.join(self.source_folder, self._source_subfolder)
        clean_dirs = [os.path.join(self.build_folder, "bin.v2"),
                      os.path.join(self.build_folder, "architecture"),
                      os.path.join(src, "dist", "bin"),
                      os.path.join(src, "stage"),
                      os.path.join(src, "tools", "build", "src", "engine", "bootstrap"),
                      os.path.join(src, "tools", "build", "src", "engine", "bin.ntx86"),
                      os.path.join(src, "tools", "build", "src", "engine", "bin.ntx86_64")]
        for d in clean_dirs:
            if os.path.isdir(d):
                self.output.warn('removing "%s"' % d)
                shutil.rmtree(d)

    def _bootstrap(self):
        """
        Bootstrap the b2 building engine from boost. It is host-specific and will be used to build the boost
        itself
        """
        folder = self._boost_build_dir
        try:
            bootstrap = "bootstrap.bat" if tools.os_info.is_windows else "./bootstrap.sh"
            with tools.vcvars(self.settings) if self._is_msvc else tools.no_op():
                self.output.info("Using %s %s" % (self.settings.compiler, self.settings.compiler.version))
                with tools.chdir(folder):
                    cmd = bootstrap
                    self.output.info(cmd)
                    envs_to_null = {
                        'AS': None, 'AR': None, 'CC': None, 'CXX': None, 'LD': None, 'RANLIB': None,
                        'ARFLAGS': None, 'CFLAGS': None, 'CXXFLAGS': None,
                        'SYSROOT': None, 'CHOST': None, 'STRIP': None,
                    }

                    # To avoid using the CXX env vars we clear them out for the build.
                    with tools.environment_append(envs_to_null):
                        self.run(cmd)

        except Exception as exc:
            self.output.warn(str(exc))
            if os.path.exists(os.path.join(folder, "bootstrap.log")):
                self.output.warn(tools.load(os.path.join(folder, "bootstrap.log")))
            raise

    def _write_user_config_jam(self):
        """
        Sets up the boost dependencies and compiler settings
        """
        self.output.info('Writing the user-config.jam file')
        contents = ''

        def create_library_config(deps_name, name):
            includedir = '"%s"' % self.deps_cpp_info[deps_name].include_paths[0].replace('\\', '/')
            libdir = '"%s"' % self.deps_cpp_info[deps_name].lib_paths[0].replace('\\', '/')
            lib = self.deps_cpp_info[deps_name].libs[0]
            version = self.deps_cpp_info[deps_name].version
            return "\nusing {name} : {version} : " \
                   "<include>{includedir} " \
                   "<search>{libdir} " \
                   "<name>{lib} ;".format(name=name,
                                          version=version,
                                          includedir=includedir,
                                          libdir=libdir,
                                          lib=lib)

        if self._zip_bzip2_requires_needed:
            contents += create_library_config('zlib', 'zlib')
            contents += create_library_config('bzip2', 'bzip2')

        # Specify here the toolset with the binary if present if don't empty parameter :
        contents += '\nusing "%s" : %s : ' % (self._toolset, self._toolset_version)
        contents += ' "%s"' % self._cxx.replace("\\", "/")

        if tools.is_apple_os(self.settings.os):
            if self.settings.compiler == "apple-clang":
                contents += " -isysroot %s" % tools.XCRun(self.settings).sdk_path
            if self.settings.get_safe("arch"):
                contents += " -arch %s" % tools.to_apple_arch(self.settings.arch)

        contents += " : \n"

        if self._ar:
            contents += '<archiver>"%s" ' % self._ar.replace("\\", "/")

        if self._ranlib:
            contents += '<ranlib>"%s" ' % self._ranlib.replace("\\", "/")

        if self._cxx_flags:
            contents += '<cxxflags>"%s" ' % self._cxx_flags

        if self._c_flags:
            contents += '<cflags>"%s" ' % self._c_flags

        if self._ld_flags:
            contents += '<linkflags>"%s" ' % self._ld_flags

        if self._as_flags:
            contents += '<asmflags>"%s" ' % self._as_flags

        contents += " ;"

        # Finally - write the config
        self.output.warn(contents)
        file_name = os.path.join(self._boost_build_dir, 'user-config.jam')
        tools.save(file_name, contents)

    @property
    def _b2_os(self):
        return {"Windows": "windows",
                "WindowsStore": "windows",
                "Linux": "linux",
                "Android": "android",
                "Macos": "darwin",
                "iOS": "iphone",
                "watchOS": "iphone",
                "tvOS": "appletv",
                "FreeBSD": "freebsd",
                "SunOS": "solatis"}.get(str(self.settings.os))

    @property
    def _b2_address_model(self):
        if str(self.settings.arch) in ["x86_64", "ppc64", "ppc64le", "mips64", "armv8", "sparcv9"]:
            return "64"
        else:
            return "32"

    @property
    def _b2_binary_format(self):
        return {"Windows": "pe",
                "WindowsStore": "pe",
                "Linux": "elf",
                "Android": "elf",
                "Macos": "mach-o",
                "iOS": "mach-o",
                "watchOS": "mach-o",
                "tvOS": "mach-o",
                "FreeBSD": "elf",
                "SunOS": "elf"}.get(str(self.settings.os))

    @property
    def _b2_architecture(self):
        if str(self.settings.arch).startswith('x86'):
            return 'x86'
        elif str(self.settings.arch).startswith('ppc'):
            return 'power'
        elif str(self.settings.arch).startswith('arm'):
            return 'arm'
        elif str(self.settings.arch).startswith('sparc'):
            return 'sparc'
        elif str(self.settings.arch).startswith('mips64'):
            return 'mips64'
        elif str(self.settings.arch).startswith('mips'):
            return 'mips1'
        else:
            return None

    @property
    def _b2_abi(self):
        if str(self.settings.arch).startswith('x86'):
            return "ms" if str(self.settings.os) in ["Windows", "WindowsStore"] else "sysv"
        elif str(self.settings.arch).startswith('ppc'):
            return "sysv"
        elif str(self.settings.arch).startswith('arm'):
            return "aapcs"
        elif str(self.settings.arch).startswith('mips'):
            return "o32"
        else:
            return None

    @property
    def _gnu_cxx11_abi(self):
        """Checks libcxx setting and returns value for the GNU C++11 ABI flag
        _GLIBCXX_USE_CXX11_ABI= .  Returns None if C++ library cannot be
        determined.
        """
        try:
            if str(self.settings.compiler.libcxx) == "libstdc++":
                return "0"
            elif str(self.settings.compiler.libcxx) == "libstdc++11":
                return "1"
        except:
            pass

        return None


    @property
    def _build_flags(self):
        flags = self._build_cross_flags

        # https://www.boost.org/doc/libs/1_70_0/libs/context/doc/html/context/architectures.html
        if self._b2_os:
            flags.append("target-os=%s" % self._b2_os)
        if self._b2_architecture:
            flags.append("architecture=%s" % self._b2_architecture)
        if self._b2_address_model:
            flags.append("address-model=%s" % self._b2_address_model)
        if self._b2_binary_format:
            flags.append("binary-format=%s" % self._b2_binary_format)
        if self._b2_abi:
            flags.append("abi=%s" % self._b2_abi)

        if self.options.layout is not "b2-default":
            flags.append("--layout=%s" % self.options.layout)

        flags.append("--user-config=%s" % os.path.join(self._boost_build_dir, 'user-config.jam'))

        def add_defines(library):
            for define in self.deps_cpp_info[library].defines:
                flags.append("define=%s" % define)

        if self._zip_bzip2_requires_needed:
            add_defines('zlib')
            add_defines('bzip2')

        if self._is_msvc and self.settings.compiler.runtime:
            flags.append('runtime-link=%s' % ('static' if 'MT' in str(self.settings.compiler.runtime) else 'shared'))

        # For details https://boostorg.github.io/build/manual/master/index.html
        flags.append("threading=%s" % ("single" if not self.options.multithreading else "multi" ))
        flags.append("visibility=%s" % self.options.visibility)

        flags.append("link=%s" % ("static" if not self.options.shared else "shared"))
        if self.settings.build_type == "Debug":
            flags.append("variant=debug")
        else:
            flags.append("variant=release")

        for libname in LIB_LIST:
            if getattr(self.options, "without_%s" % libname):
                flags.append("--without-%s" % libname)

        # CXX FLAGS
        cxx_flags = []
        if self.settings.get_safe("compiler.cppstd"):
            cxx_flags.append(cppstd_flag(self.settings))

        # fPIC DEFINITION
        if self.settings.os != "Windows":
            if self.options.fPIC:
                cxx_flags.append("-fPIC")
        if self.settings.build_type == "RelWithDebInfo":
            if self.settings.compiler == "gcc" or "clang" in str(self.settings.compiler):
                cxx_flags.append("-g")
            elif self.settings.compiler == "Visual Studio":
                cxx_flags.append("/Z7")

        # Standalone toolchain fails when declare the std lib
        if self.settings.os != "Android" and self.settings.os != "Emscripten":
            try:
                if self._gnu_cxx11_abi:
                    flags.append("define=_GLIBCXX_USE_CXX11_ABI=%s" % self._gnu_cxx11_abi)

                if "clang" in str(self.settings.compiler):
                    if str(self.settings.compiler.libcxx) == "libc++":
                        cxx_flags.append("-stdlib=libc++")
                        flags.append('linkflags="-stdlib=libc++"')
                    else:
                        cxx_flags.append("-stdlib=libstdc++")
            except:
                pass

        if self.options.error_code_header_only:
            flags.append("define=BOOST_ERROR_CODE_HEADER_ONLY=1")
        if self.options.system_no_deprecated:
            flags.append("define=BOOST_SYSTEM_NO_DEPRECATED=1")
        if self.options.asio_no_deprecated:
            flags.append("define=BOOST_ASIO_NO_DEPRECATED=1")
        if self.options.filesystem_no_deprecated:
            flags.append("define=BOOST_FILESYSTEM_NO_DEPRECATED=1")
        if self.options.segmented_stacks:
            flags.extend(["segmented-stacks=on",
                          "define=BOOST_USE_SEGMENTED_STACKS=1",
                          "define=BOOST_USE_UCONTEXT=1"])

        if tools.is_apple_os(self.settings.os):
            if self.settings.get_safe("os.version"):
                cxx_flags.append(tools.apple_deployment_target_flag(self.settings.os, self.settings.os.version))

        if self.settings.os == "iOS":
            # One of the *_USE_PTHREADS flags causes iOS applications to crash when using boost::log
            # if self.options.multithreading:
            #     cxx_flags.append("-DBOOST_AC_USE_PTHREADS")
            #     cxx_flags.append("-DBOOST_SP_USE_PTHREADS")

            # Bitcode flag will be added automatically in darwin-toolchain
            # cxx_flags.append("-fembed-bitcode")

        cxx_flags = 'cxxflags="%s"' % " ".join(cxx_flags) if cxx_flags else ""
        flags.append(cxx_flags)

        if self.options.extra_b2_flags:
            flags.append(str(self.options.extra_b2_flags))

        flags.extend(["install", "--prefix=%s" % self.package_folder, "-j%s" % tools.cpu_count(), "--abbreviate-paths"])
        if self.options.debug_level:
            flags.append("-d%d" % self.options.debug_level)
        return flags

    @property
    def _build_cross_flags(self):
        flags = []
        if not tools.cross_building(self.settings):
            return flags

        arch = self.settings.get_safe('arch')
        if arch.startswith('arm'):
            if 'hf' in arch:
                flags.append('-mfloat-abi=hard')
        elif self.settings.os == "Emscripten":
            pass
        elif arch in ["x86", "x86_64"]:
            pass
        elif arch.startswith("ppc"):
            pass
        elif arch.startswith("mips"):
            pass
        else:
            self.output.warn("Unable to detect the appropriate ABI for %s architecture." % arch)

        self.output.info("Cross building flags: %s" % flags)
        return flags

    def package(self):
        self.copy("LICENSE_1_0.txt", dst="licenses", src=os.path.join(self.source_folder,
                                                                      self._source_subfolder))

        if self.options.header_only:
            self.copy(pattern="*", dst="include/boost", src="%s/boost" % self._boost_dir)

    def package_info(self):
        gen_libs = [] if self.options.header_only else tools.collect_libs(self)

        if self._is_versioned_layout:
            version_tokens = str(self.version).split(".")
            if len(version_tokens) >= 2:
                major = version_tokens[0]
                minor = version_tokens[1]
                boost_version_tag = "boost-%s_%s" % (major, minor)
                self.cpp_info.includedirs = [os.path.join(self.package_folder, "include", boost_version_tag)]

        # List of lists, so if more than one matches the lib like serialization and wserialization
        # both will be added to the list
        ordered_libs = [[] for _ in range(len(LIB_LIST))]

        # The order is important, reorder following the LIB_LIST order
        missing_order_info = []
        for real_lib_name in gen_libs:
            for pos, alib in enumerate(LIB_LIST):
                if os.path.splitext(real_lib_name)[0].split("-")[0].endswith(alib):
                    ordered_libs[pos].append(real_lib_name)
                    break
            else:
                # self.output.info("Missing in order: %s" % real_lib_name)
                if "_exec_monitor" not in real_lib_name:  # https://github.com/bincrafters/community/issues/94
                    missing_order_info.append(real_lib_name)  # Assume they do not depend on other

        # Flat the list and append the missing order
        self.cpp_info.libs = [item for sublist in ordered_libs
                                      for item in sublist if sublist] + missing_order_info

        if self.options.without_test:  # remove boost_unit_test_framework
            self.cpp_info.libs = [lib for lib in self.cpp_info.libs if "unit_test" not in lib]

        self.output.info("LIBRARIES: %s" % self.cpp_info.libs)
        self.output.info("Package folder: %s" % self.package_folder)

        if not self.options.header_only and self.options.shared:
            self.cpp_info.defines.append("BOOST_ALL_DYN_LINK")

        if self.options.system_no_deprecated:
            self.cpp_info.defines.append("BOOST_SYSTEM_NO_DEPRECATED")

        if self.options.asio_no_deprecated:
            self.cpp_info.defines.append("BOOST_ASIO_NO_DEPRECATED")

        if self.options.filesystem_no_deprecated:
            self.cpp_info.defines.append("BOOST_FILESYSTEM_NO_DEPRECATED")

        if self.options.segmented_stacks:
            self.cpp_info.defines.extend(["BOOST_USE_SEGMENTED_STACKS", "BOOST_USE_UCONTEXT"])

        if self.settings.os != "Android":
            if self._gnu_cxx11_abi:
                self.cpp_info.defines.append("_GLIBCXX_USE_CXX11_ABI=%s" % self._gnu_cxx11_abi)

        if not self.options.header_only:
            if self.options.error_code_header_only:
                self.cpp_info.defines.append("BOOST_ERROR_CODE_HEADER_ONLY")

            if self.options.shared:
                self.cpp_info.defines.append("BOOST_ALL_DYN_LINK")
            else:
                self.cpp_info.defines.append("BOOST_USE_STATIC_LIBS")
                if not self.options.without_python:
                    self.cpp_info.defines.append("BOOST_PYTHON_STATIC_LIB")

            if self._is_msvc or self._is_clang_cl:
                if not self.options.magic_autolink:
                    # DISABLES AUTO LINKING! NO SMART AND MAGIC DECISIONS THANKS!
                    self.cpp_info.defines.append("BOOST_ALL_NO_LIB")
                    self.output.info("Disabled magic autolinking (smart and magic decisions)")
                else:
                    if self.options.layout == "system":
                        self.cpp_info.defines.append("BOOST_AUTO_LINK_SYSTEM")
                    elif self.options.layout == "tagged":
                        self.cpp_info.defines.append("BOOST_AUTO_LINK_TAGGED")
                    self.output.info("Enabled magic autolinking (smart and magic decisions)")

                # https://github.com/conan-community/conan-boost/issues/127#issuecomment-404750974
                self.cpp_info.system_libs.append("bcrypt")
            elif self.settings.os == "Linux":
                # https://github.com/conan-community/community/issues/135
                self.cpp_info.system_libs.append("rt")
                if self.options.multithreading:
                    self.cpp_info.system_libs.append("pthread")
            elif self.settings.os == "Emscripten":
                if self.options.multithreading:
                    arch = self.settings.get_safe('arch')
                    # https://emscripten.org/docs/porting/pthreads.html
                    # The documentation mentions that we should be using the "-s USE_PTHREADS=1"
                    # but it was causing problems with the target based configurations in conan
                    # So instead we are using the raw compiler flags (that are being activated
                    # from the aformentioned flag)
                    if arch.startswith("x86") or arch.startswith("wasm"):
                        self.cpp_info.cxxflags.append("-pthread")
                        self.cpp_info.sharedlinkflags.extend(["-pthread","--shared-memory"])
                        self.cpp_info.exelinkflags.extend(["-pthread","--shared-memory"])
        else:
            if self.options.error_code_header_only:
                self.cpp_info.defines.append("BOOST_ERROR_CODE_HEADER_ONLY")
                self.cpp_info.defines.append("BOOST_SYSTEM_NO_LIB")

        if str(self.settings.os) in ['watchOS', 'tvOS']:
            # 'sigaltstack' is unavailable: not available on tvOS / watchOS
            self.cpp_info.defines.append("BOOST_TEST_DISABLE_ALT_STACK=1")

        boost_root = self.package_folder
        boost_include = os.path.join(boost_root, 'include')
        boost_lib = os.path.join(boost_root, 'lib')

        self.env_info.BOOST_ROOT = boost_root
        self.env_info.BOOST_INCLUDEDIR = boost_include
        self.env_info.BOOST_LIBRARYDIR = boost_lib

        self.cpp_info.bindirs.append("lib")
        self.cpp_info.names["cmake_find_package"] = "Boost"
        self.cpp_info.names["cmake_find_package_multi"] = "Boost"
