from conan.packager import ConanMultiPackager

if __name__ == "__main__":
    builder = ConanMultiPackager()
    builder.add(settings={"compiler.cppstd": "17"})
    builder.run()
