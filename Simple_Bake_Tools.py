bl_info = {
    "name": "Simple Bake Tools",
    "author": "za-ne12",
    "version": (0, 4, 0),
    "blender": (5, 2, 3),
    "location": "View3D > Sidebar > Simple Bake",
    "category": "Material",
    "description": "Smart UV + bake selected maps to images + build baked material (Blender 5.2.3-safe)",
}

import bpy
import os
import math
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    StringProperty,
    PointerProperty,
    EnumProperty,
)


# -----------------------------
# Core helpers (Blender 5.2.3)
# -----------------------------

def ensure_cycles(scene: bpy.types.Scene):
    if scene.render.engine != "CYCLES":
        scene.render.engine = "CYCLES"


def active_mesh_obj(context):
    obj = context.active_object
    if not obj or obj.type != "MESH":
        return None
    return obj


def object_bake_type_identifiers():
    prop = bpy.ops.object.bake.get_rna_type().properties["type"]
    return {e.identifier for e in prop.enum_items}


def ensure_uv_and_smart_project(context, obj, angle_limit_deg=66.0, island_margin=0.02):
    angle_limit_rad = math.radians(angle_limit_deg)

    if context.object and context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    vl = context.view_layer
    for o in vl.objects:
        o.select_set(False)
    obj.select_set(True)
    vl.objects.active = obj

    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    if me.uv_layers.active is None:
        me.uv_layers.active = me.uv_layers[0]

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(
        angle_limit=angle_limit_rad,
        island_margin=island_margin,
        area_weight=0.0,
        correct_aspect=True,
        scale_to_bounds=False,
    )
    bpy.ops.object.mode_set(mode="OBJECT")


def new_image(name, size, is_data):
    img = bpy.data.images.new(name=name, width=size, height=size, alpha=True, float_buffer=False)

    try:
        img.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
    except Exception:
        pass
    return img


def ensure_dir(path_abs):
    os.makedirs(path_abs, exist_ok=True)


def save_image(img, folder_abs, filename_base, file_format, pack=False, save_to_disk=False):
    if pack:
        img.pack()

    if not save_to_disk:
        return

    # Map enum to actual extensions
    ext_map = {
        "PNG": ".png",
        "JPEG": ".jpg",
        "TARGA": ".tga",
        "OPEN_EXR": ".exr"
    }
    ext = ext_map.get(file_format, ".png")
    filename = filename_base + ext

    img.filepath_raw = os.path.join(folder_abs, filename)
    img.file_format = file_format
    try:
        img.save()
    except Exception as e:
        print(f"Failed to save {filename}: {e}")


def ensure_material(obj):
    # In Blender 5.2.3, materials always have a native node_tree (use_nodes removed in 5.0+)
    mat = obj.active_material
    if not mat and obj.data.materials:
        mat = obj.data.materials[0]
        obj.active_material_index = 0

    if not mat:
        mat = bpy.data.materials.new(name=f"{obj.name}_Source")
        obj.data.materials.append(mat)
        obj.active_material_index = len(obj.data.materials) - 1

    return mat


def ensure_active_image_node(mat, node_name, image):
    nt = mat.node_tree
    nodes = nt.nodes

    node = nodes.get(node_name)
    if not node:
        node = nodes.new("ShaderNodeTexImage")
        node.name = node_name
        node.label = node_name
        node.location = (-800, 0)

    node.image = image

    for n in nodes:
        n.select = False
    node.select = True
    nt.nodes.active = node
    return node


def cleanup_temp_bake_nodes(mat, temp_node_names):
    if not mat or not mat.node_tree:
        return
    nodes = mat.node_tree.nodes
    for name in temp_node_names:
        node = nodes.get(name)
        if node:
            nodes.remove(node)


def safe_setattr(obj, name, value):
    if hasattr(obj, name):
        setattr(obj, name, value)


def setup_bake_settings(scene, margin, clear=True):
    bs = scene.render.bake
    safe_setattr(bs, "target", "IMAGE_TEXTURES")
    safe_setattr(bs, "margin", margin)
    safe_setattr(bs, "use_clear", clear)


def build_baked_material(obj, images, multiply_ao=True):
    # Blender 5.2.3 initializes mat.node_tree automatically
    mat = bpy.data.materials.new(name=f"{obj.name}_Baked")
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    for n in list(nodes):
        nodes.remove(n)

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (350, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    base = None
    ao = None

    if "combined" in images:
        base = nodes.new("ShaderNodeTexImage")
        base.image = images["combined"]
        base.location = (-450, 250)
    elif "basecolor" in images:
        base = nodes.new("ShaderNodeTexImage")
        base.image = images["basecolor"]
        base.location = (-450, 250)

    if "ao" in images:
        ao = nodes.new("ShaderNodeTexImage")
        ao.image = images["ao"]
        ao.location = (-450, 0)

    if base and ao and multiply_ao:
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.location = (-120, 180)
        links.new(base.outputs["Color"], mix.inputs["A"])
        links.new(ao.outputs["Color"], mix.inputs["B"])
        links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    elif base:
        links.new(base.outputs["Color"], bsdf.inputs["Base Color"])

    if "roughness" in images:
        r = nodes.new("ShaderNodeTexImage")
        r.image = images["roughness"]
        r.location = (-450, -250)
        links.new(r.outputs["Color"], bsdf.inputs["Roughness"])

    if "emission" in images:
        e = nodes.new("ShaderNodeTexImage")
        e.image = images["emission"]
        e.location = (-450, -500)
        links.new(e.outputs["Color"], bsdf.inputs["Emission Color"])
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = 1.0

    if "normal" in images:
        nimg = nodes.new("ShaderNodeTexImage")
        nimg.image = images["normal"]
        nimg.location = (-450, -760)

        nmap = nodes.new("ShaderNodeNormalMap")
        nmap.location = (-120, -760)
        links.new(nimg.outputs["Color"], nmap.inputs["Color"])
        links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


# -----------------------------
# Settings
# -----------------------------

class SBT_Settings(PropertyGroup):

    smart_uv: BoolProperty(name="Smart UV Before Bake", default=True)
    uv_angle_limit_deg: FloatProperty(name="UV Angle Limit (deg)", default=66.0, min=1.0, max=89.0)
    uv_island_margin: FloatProperty(name="UV Island Margin", default=0.02, min=0.0, max=1.0)

    tex_size: IntProperty(name="Texture Size", default=2048, min=128, max=16384)
    bake_margin: IntProperty(name="Bake Margin", default=16, min=0, max=256)

    bake_combined: BoolProperty(name="Combined", default=False)
    bake_basecolor: BoolProperty(name="Diffuse Color (Base Color)", default=True)
    bake_normal: BoolProperty(name="Normal", default=True)
    bake_roughness: BoolProperty(name="Roughness", default=False)
    bake_emission: BoolProperty(name="Emission", default=False)
    bake_ao: BoolProperty(name="Ambient Occlusion", default=False)

    normal_space: EnumProperty(
        name="Normal Space",
        items=[
            ("TANGENT", "Tangent", "Tangent space normals (game-ready)"),
            ("OBJECT", "Object", "Object space normals"),
        ],
        default="TANGENT",
    )

    create_new_material: BoolProperty(name="Create & Assign Baked Material", default=True)
    ao_multiply_base: BoolProperty(name="Multiply AO into Base Color", default=True)

    pack_images: BoolProperty(name="Pack Images into .blend", default=False)
    save_to_disk: BoolProperty(name="Save Images to Disk", default=False)
    image_format: EnumProperty(
        name="File Format",
        items=[
            ("PNG", "PNG", ""),
            ("JPEG", "JPEG", ""),
            ("TARGA", "Targa", ""),
            ("OPEN_EXR", "OpenEXR", "")
        ],
        default="PNG"
    )
    output_dir: StringProperty(name="Output Folder", subtype="DIR_PATH", default="//bakes/")


# -----------------------------
# Operator
# -----------------------------

class SBT_OT_bake_selected(Operator):
    bl_idname = "sbt.bake_selected"
    bl_label = "Smart UV + Bake"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if hasattr(bpy.app, "is_job_running") and bpy.app.is_job_running("OBJECT_BAKE"):
            self.report({"WARNING"}, "An object bake job is already running.")
            return {"CANCELLED"}

        scene = context.scene
        s = scene.sbt_settings

        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected_meshes:
            self.report({"ERROR"}, "Select at least one MESH object.")
            return {"CANCELLED"}

        ensure_cycles(scene)

        available = object_bake_type_identifiers()

        required = []
        if s.bake_combined: required.append("COMBINED")
        if s.bake_basecolor: required.append("DIFFUSE")
        if s.bake_normal: required.append("NORMAL")
        if s.bake_roughness: required.append("ROUGHNESS")
        if s.bake_emission: required.append("EMIT")
        if s.bake_ao: required.append("AO")

        missing = [t for t in required if t not in available]
        if missing:
            self.report({"ERROR"}, f"Missing bake types exposed by bpy.ops.object.bake: {missing}")
            return {"CANCELLED"}

        setup_bake_settings(scene, margin=s.bake_margin, clear=True)

        bs = scene.render.bake
        safe_setattr(bs, "normal_space", s.normal_space)

        vl = context.view_layer

        # Unselect all to start fresh
        for o in vl.objects:
            o.select_set(False)

        size = s.tex_size

        for obj in selected_meshes:
            # Isolate the current object for processing
            obj.select_set(True)
            vl.objects.active = obj

            if s.smart_uv:
                ensure_uv_and_smart_project(context, obj, s.uv_angle_limit_deg, s.uv_island_margin)

            src_mat = ensure_material(obj)

            images = {}
            if s.bake_combined:
                images["combined"] = new_image(f"{obj.name}_Combined", size, is_data=False)
            if s.bake_basecolor:
                images["basecolor"] = new_image(f"{obj.name}_BaseColor", size, is_data=False)
            if s.bake_normal:
                images["normal"] = new_image(f"{obj.name}_Normal", size, is_data=True)
            if s.bake_roughness:
                images["roughness"] = new_image(f"{obj.name}_Roughness", size, is_data=True)
            if s.bake_emission:
                images["emission"] = new_image(f"{obj.name}_Emission", size, is_data=False)
            if s.bake_ao:
                images["ao"] = new_image(f"{obj.name}_AO", size, is_data=True)

            if not images:
                self.report({"ERROR"}, "No maps selected.")
                return {"CANCELLED"}

            temp_nodes = []
            try:
                if "combined" in images:
                    temp_nodes.append("SBT_TARGET_combined")
                    ensure_active_image_node(src_mat, "SBT_TARGET_combined", images["combined"])
                    bpy.ops.object.bake(type="COMBINED")

                if "basecolor" in images:
                    temp_nodes.append("SBT_TARGET_basecolor")
                    ensure_active_image_node(src_mat, "SBT_TARGET_basecolor", images["basecolor"])
                    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})

                if "normal" in images:
                    temp_nodes.append("SBT_TARGET_normal")
                    ensure_active_image_node(src_mat, "SBT_TARGET_normal", images["normal"])
                    bpy.ops.object.bake(type="NORMAL")

                if "ao" in images:
                    temp_nodes.append("SBT_TARGET_ao")
                    ensure_active_image_node(src_mat, "SBT_TARGET_ao", images["ao"])
                    bpy.ops.object.bake(type="AO")

                if "roughness" in images:
                    temp_nodes.append("SBT_TARGET_roughness")
                    ensure_active_image_node(src_mat, "SBT_TARGET_roughness", images["roughness"])
                    bpy.ops.object.bake(type="ROUGHNESS")

                if "emission" in images:
                    temp_nodes.append("SBT_TARGET_emission")
                    ensure_active_image_node(src_mat, "SBT_TARGET_emission", images["emission"])
                    bpy.ops.object.bake(type="EMIT")
            finally:
                cleanup_temp_bake_nodes(src_mat, temp_nodes)

            if s.create_new_material:
                baked_mat = build_baked_material(obj, images, multiply_ao=s.ao_multiply_base)
                if obj.data.materials:
                    obj.data.materials[obj.active_material_index] = baked_mat
                else:
                    obj.data.materials.append(baked_mat)

            if s.save_to_disk or s.pack_images:
                out_dir_abs = bpy.path.abspath(s.output_dir) if s.save_to_disk else ""
                if s.save_to_disk:
                    ensure_dir(out_dir_abs)
                for key, img in images.items():
                    save_image(img, out_dir_abs, f"{obj.name}_{key}", s.image_format, pack=s.pack_images, save_to_disk=s.save_to_disk)

            # Deselect current object before next iteration
            obj.select_set(False)

        # Reselect original objects
        for obj in selected_meshes:
            obj.select_set(True)
        if selected_meshes:
            vl.objects.active = selected_meshes[0]

        self.report({"INFO"}, f"Bake complete for {len(selected_meshes)} object(s).")
        return {"FINISHED"}


# -----------------------------
# UI Panel
# -----------------------------

class SBT_PT_panel(Panel):
    bl_label = "Simple Bake Tools"
    bl_idname = "SBT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simple Bake"

    def draw(self, context):
        s = context.scene.sbt_settings
        layout = self.layout

        box = layout.box()
        box.label(text="Maps", icon="TEXTURE_DATA")
        col = box.column(align=True)
        col.prop(s, "bake_combined")
        col.prop(s, "bake_basecolor")
        col.prop(s, "bake_normal")
        col.prop(s, "bake_roughness")
        col.prop(s, "bake_emission")
        col.prop(s, "bake_ao")

        box = layout.box()
        box.label(text="UV Settings", icon="UV_DATA")
        box.prop(s, "smart_uv")
        sub = box.column(align=True)
        sub.enabled = s.smart_uv
        sub.prop(s, "uv_angle_limit_deg")
        sub.prop(s, "uv_island_margin")

        box = layout.box()
        box.label(text="Bake Settings", icon="RENDER_RESULT")
        box.prop(s, "tex_size")
        box.prop(s, "bake_margin")
        box.prop(s, "normal_space")

        box = layout.box()
        box.label(text="Output", icon="FILE_FOLDER")
        box.prop(s, "create_new_material")
        box.prop(s, "ao_multiply_base")
        box.prop(s, "pack_images")
        box.prop(s, "save_to_disk")
        sub2 = box.column(align=True)
        sub2.enabled = s.save_to_disk
        sub2.prop(s, "image_format")
        sub2.prop(s, "output_dir")

        layout.separator()
        layout.operator("sbt.bake_selected", text="Bake Selected Objects", icon="RENDER_STILL")


# -----------------------------
# Register
# -----------------------------

classes = (
    SBT_Settings,
    SBT_OT_bake_selected,
    SBT_PT_panel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.sbt_settings = PointerProperty(type=SBT_Settings)

def unregister():
    del bpy.types.Scene.sbt_settings
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
