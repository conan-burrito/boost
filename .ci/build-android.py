from conan.packager import ConanMultiPackager

if __name__ == "__main__":
    builder = ConanMultiPackager()
    builder.add(settings={"arch": "armv7", "os.api_level": "16"})
    builder.add(settings={"arch": "armv8", "os.api_level": "21"})
    builder.add(settings={"arch": "x86", "os.api_level": "16"})
    builder.add(settings={"arch": "x86_64", "os.api_level": "21"})
    builder.run()
