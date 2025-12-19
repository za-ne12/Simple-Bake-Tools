# Simple Bake Tools (Blender Add-on)

A lightweight Blender add-on for **one-click Smart UV + texture baking** that:
- uses the **active selected mesh**
- optionally generates a **Smart UV Project** UV map before baking
- bakes selected passes (Diffuse/Base Color, Normal, Roughness, Emission, AO)
- creates **Image Texture datablocks**
- builds and assigns a **new baked material** wired to the baked images
- optionally saves baked maps to disk as PNGs

## Features

- ✅ Smart UV Project (auto UV unwrap) before baking
- ✅ Bake selected maps:
  - Diffuse Color (Base Color only)
  - Normal
  - Roughness
  - Emission
  - Ambient Occlusion
- ✅ Auto-create baked images (per map)
- ✅ Auto-create a baked material (Principled BSDF) and wire maps
- ✅ Optional AO multiply into Base Color
- ✅ Optional save-to-disk (PNG) to a chosen folder
- ✅ Blender 5-safe bake-type detection via operator RNA
- **Active material only**: if the object has multiple materials, this currently bakes based on the active material context.
  
## Requirements

- Blender **5.0+**

## Installation

- Add to Blender Add-ons folder and enable
