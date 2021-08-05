from cpt.packager import ConanMultiPackager

if __name__ == "__main__":
    builder = ConanMultiPackager()
    builder.add(settings={"arch": "asm.js"})
    builder.add(settings={"arch": "wasm"})
    builder.run()
