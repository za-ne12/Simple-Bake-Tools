# Simple Bake Tools (Blender Add-on)

A lightweight Blender add-on for **one-click Smart UV + texture baking** that:
- processes **multiple selected meshes**
- optionally generates a **Smart UV Project** UV map before baking
- bakes selected passes (Combined, Diffuse/Base Color, Normal, Roughness, Emission, AO)
- creates **Image Texture datablocks**
- builds and assigns a **new baked material** wired to the baked images
- optionally packs maps into the .blend or saves baked maps to disk in various formats

## Features

- ✅ Smart UV Project (auto UV unwrap) before baking
- ✅ **Batch Processing**: Bake multiple selected objects sequentially
- ✅ Bake selected maps:
  - **Combined**
  - Diffuse Color (Base Color only)
  - Normal
  - Roughness
  - Emission
  - Ambient Occlusion
- ✅ Auto-create baked images (per map)
- ✅ Auto-create a baked material (Principled BSDF) and wire maps (Combined and Base Color)
- ✅ Optional AO multiply into Base Color
- ✅ **Pack Images**: Automatically pack baked textures into the `.blend` file
- ✅ Optional save-to-disk to a chosen folder with multiple file formats (PNG, JPEG, Targa, OpenEXR)
- ✅ Blender 5-safe bake-type detection via operator RNA
- **Active material only**: if the object has multiple materials, this currently bakes based on the active material context.
- **Revamped UI**: Organized panel layout with distinct groups for Maps, UV Settings, Bake Settings, and Output options.
  
## Requirements

- Blender **5.2.3+**

## Installation

- Add to Blender Add-ons folder and enable
