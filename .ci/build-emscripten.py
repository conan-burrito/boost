from cpt.packager import ConanMultiPackager

if __name__ == "__main__":
    builder = ConanMultiPackager()
    builder.add(settings={"arch": "asm.js"}, options={"boost:header_only": True})
    builder.add(settings={"arch": "wasm"}, options={"boost:header_only": True})
    builder.run()
