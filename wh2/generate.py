import csv
import os
import shutil
import subprocess
import argparse

game_name = "warhammer_2"
extract_path = "extract"
output_path = "output"
template_path = "template"
mod_name = "More unit stats"
install_path = os.path.expanduser("~") + f"/Documents/TWMods/{game_name}/{mod_name}.pack"
game_path = "E:/SteamLibrary/steamapps/common/Total War WARHAMMER II"

arg_parser = argparse.ArgumentParser(description="Generates the mod packfile to Documents/TWMods/")
arg_parser.add_argument("path_to_rpfm_cli", help="path to rpfm_cli.exe used for extracting and creating mod files")
arg_parser.add_argument("-g", dest="path_to_game", default=game_path, help=f"path to the main directory of {game_name}(default: {game_path})")
arg_parser.add_argument("-i", dest="install_path", default=install_path, help=f"path where to install the mod file (default: {install_path})")

init_args = arg_parser.parse_args()

rpfmcli_path = init_args.path_to_rpfm_cli
game_path = init_args.path_to_game
install_path = init_args.install_path


def run_rpfm(packfile, *args):
    subprocess.run([rpfmcli_path, "-v", "-g", game_name, "-p", packfile, *args], check=True)


def extract_packfiles():
    shutil.rmtree(extract_path, ignore_errors=True)
    shutil.rmtree(output_path, ignore_errors=True)
    os.makedirs(extract_path, exist_ok=True)
    run_rpfm(f"{game_path}/data/data.pack", "packfile", "-E", extract_path, "dummy", "db")
    run_rpfm(f"{game_path}/data/local_en.pack", "packfile", "-E", extract_path, "dummy", "text")


def make_package():
    shutil.copytree(template_path, output_path, dirs_exist_ok=True)
    os.makedirs(os.path.dirname(install_path), exist_ok=True)
    try:
        os.remove(install_path)
    except:
        pass
    run_rpfm(install_path, "packfile", "-n")
    for root, dirs, files in os.walk(output_path + "/db", topdown=False):
        relroot = os.path.relpath(root, output_path + "/db")
        for name in files:
            subprocess.run([rpfmcli_path, "-v", "-g", game_name, "-p", install_path, "packfile", "-a", "db", relroot.replace("\\", "/") + "/" + name], cwd=output_path + "/db", check=True)
    for root, dirs, files in os.walk(output_path + "/text", topdown=False):
        relroot = os.path.relpath(root, output_path + "/text")
        for name in files:
            subprocess.run([rpfmcli_path, "-v", "-g", game_name, "-p", install_path, "packfile", "-a", "text", relroot.replace("\\", "/") + "/" + name], cwd=output_path + "/text", check=True)
    for root, dirs, files in os.walk(output_path + "/ui", topdown=False):
        relroot = os.path.relpath(root, output_path + "/ui")
        for name in files:
            subprocess.run([rpfmcli_path, "-v", "-g", game_name, "-p", install_path, "packfile", "-a", "ui", relroot.replace("\\", "/") + "/" + name], cwd=output_path + "/ui", check=True)

    # todo: fix slashes in final print
    run_rpfm(install_path, "packfile", "-l")
    print(f"Mod package written to: {install_path}")


def extract_db_to_tsv(packfile, tablefile):
    run_rpfm(f"{game_path}/data/{packfile}", "table", "-e", tablefile)


def pack_tsv_to_db(packfile, tablefile):
    run_rpfm(f"{game_path}/data/{packfile}", "table", "-i", tablefile)


class TWDBRow:
    def __init__(self, key_ids, row):
        self.key_ids = key_ids
        self.row = row

    def __getitem__(self, key):
        return self.row[self.key_ids[key]]

    def __setitem__(self, key, value):
        self.row[self.key_ids[key]] = value

    def copy(self):
        return TWDBRow(self.key_ids, self.row.copy())


class TWDBReaderImpl:
    def __init__(self):
        self.table_name = None
        self.out_tsv_file = None
        self.table_file = None
        self.packfile = None
        self.tsv_file = None
        self.tsv_file_path = None

    def _read_header(self):
        try:
            self.tsv_file = open(f"{extract_path}/{self.tsv_file_path}", encoding="utf-8")
        except FileNotFoundError:
            extract_db_to_tsv(self.packfile, f"{extract_path}/{self.table_file}")
            self.tsv_file = open(f"{extract_path}/{self.tsv_file_path}", encoding="utf-8")

        self.read_tsv = csv.reader(self.tsv_file, delimiter="\t")
        self.head_rows = []
        self.head_rows.append(next(self.read_tsv))
        self.head_rows.append(next(self.read_tsv))
        self.key_ids = {}
        i = 0
        for key in self.head_rows[0]:
            self.key_ids[key] = i
            i = i + 1

    def __enter__(self):
        self._read_header()
        self.rows_iter = map(lambda row: TWDBRow(self.key_ids, row), self.read_tsv)
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.tsv_file.close()

    def make_writer(self):
        if self.head_rows is None:
            self._read_header()
            self.tsv_file.close()
        out_tsv_file = self.tsv_file_path
        if self.out_tsv_file is not None:
            out_tsv_file = self.out_tsv_file
        return TWDBWriter(self.table_name, self.table_file, out_tsv_file, self.packfile, self.head_rows, self.key_ids)

    def data_into_writer(self):
        result = self.make_writer()
        with self as db_reader:
            for row in db_reader.rows_iter:
                result.new_rows.append(row)
        return result


class TWDBReader(TWDBReaderImpl):
    def __init__(self, table_name):
        super().__init__()
        self.table_name = table_name
        self.table_file = "db/" + self.table_name + "/data__"
        self.tsv_file_path = self.table_file + ".tsv"
        self.out_tsv_file = None
        self.head_rows = None
        self.packfile = "data.pack"


class TWLocDBReader(TWDBReaderImpl):
    def __init__(self, table_name):
        super().__init__()
        self.table_name = table_name
        self.table_file = f"text/db/{self.table_name}__.loc"
        self.tsv_file_path = f"text/db/{self.table_name}__.tsv"
        self.out_tsv_file = f"text/db/{self.table_name}__.loc.tsv"
        self.head_rows = None
        self.packfile = "local_en.pack"


class TWDBWriter:
    def __init__(self, table_name, table_file, tsv_file_path, packfile, head_rows, key_ids):
        self.tsv_file = None
        self.tsv_writer = None
        self.table_name = table_name
        self.table_file = table_file
        self.tsv_file_path = tsv_file_path
        self.head_rows = head_rows
        self.key_ids = key_ids
        self.new_rows = []
        self.packfile = packfile

    def write(self):
        os.makedirs(os.path.dirname(f"{output_path}/{self.tsv_file_path}"), exist_ok=True)
        self.tsv_file = open(f"{output_path}/{self.tsv_file_path}", 'w', newline="", encoding="utf-8")
        self.tsv_writer = csv.writer(self.tsv_file, delimiter='\t', quoting=csv.QUOTE_NONE, quotechar='')
        for row in self.head_rows:
            self.tsv_writer.writerow(row)
        for row in self.new_rows:
            self.tsv_writer.writerow(row.row)
        self.tsv_file.close()
        pack_tsv_to_db(self.packfile, f"{output_path}/{self.tsv_file_path}")
        os.remove(f"{output_path}/{self.tsv_file_path}")

    def make_row(self, kv=None):
        if kv is None:
            kv = {}
        row_val = [""] * len(self.head_rows[1])
        row = TWDBRow(self.key_ids, row_val)
        for key in kv:
            row[key] = kv[key]
        return row

    def proto_row(self):
        return self.new_rows[0].copy()


def read_to_dict(db_reader, key="key"):
    result = {}
    with db_reader:
        for row in db_reader.rows_iter:
            result[row[key]] = row
    return result


def read_to_dict_of_dicts_of_lists(db_reader, key1, key2):
    result = {}
    with db_reader:
        for row in db_reader.rows_iter:
            val1 = row[key1]
            if val1 not in result:
                result[val1] = {}
            val2 = row[key2]
            if val2 not in result[val1]:
                result[val1][val2] = []
            result[val1][val2].append(row)
    return result


def read_to_dict_of_lists(db_reader, key="key"):
    result = {}
    with db_reader:
        for row in db_reader.rows_iter:
            if row[key] not in result:
                result[row[key]] = []
            result[row[key]].append(row)
    return result


def read_column_to_dict(db_reader, key, column):
    result = {}
    with db_reader:
        for row in db_reader.rows_iter:
            result[row[key]] = row[column]
    return result


def read_column_to_dict_of_lists(db_reader, key, column):
    result = {}
    with db_reader:
        for row in db_reader.rows_iter:
            if row[key] not in result:
                result[row[key]] = []
            result[row[key]].append(row[column])
    return result


# ability phase details - done
# requested_stance -> special_ability_stance_enums - just an animation?
# fatigue_change_ratio: This is a scalar that changes the unit's fatigue (once off) relative to the maximum. For example, -0.25 will reduce it by 25% and 1.1 will increase it by 10%
# inspiration_aura_range_mod
# ability_recharge_change: if the unit has abilities, their recharge will be changed by that amount (negative will reduce the time, positive will increase the time)
# resurrect: If ticked, when healing excess hit points will resurrect dead soldiers
# hp_change_frequency: In seconds, how often hp (hit point) change should attempt to be applied
# heal_amount: When HP (hit points) are healed, how much total should be changed, spread amongst the entities
# damage_chance: Per entity, per frequency, what the chance is of applying damage; the effect is not linear, most effective in 0.00-0.02
# damage_amount: Per entity, per frequency, what the amount of damage to apply
# max_damaged_entities: Per damage/heal frequency, how many entities can we affect (negative is no limit)
# mana_regen_mod: How much we add to the current recharge for mana per second
# mana_max_depletion_mod: How much is added to the current value for max mana depletion
# imbue_magical: Does this phase imbue the target with magical attacks?
# imbue_ignition: Does this phase imbue the target with flaming attacks?
# imbue_contact: -> special_ability_phases Does this phase imbue the target with a contact phase when attacking?
# recharge_time
# is_hidden_in_ui
# affects_allies
# affects_enemies
# replenish_ammo: How much ammunition is replenished when the phase starts (negative values will spend ammo instead), this value is a percentage of unit max ammo
def ability_damage_stat(base, ignition, magic, title="dmg"):
    type_str = ""
    if magic == "true":
        type_str += "[[img:ui/skins/default/modifier_icon_magical.png]][[/img]]"
    if float(ignition) != 0:
        type_str += "[[img:ui/skins/default/modifier_icon_flaming.png]][[/img]]"
    return title + ": " + stat_str(base) + type_str


def ability_phase_details_stats(phase_id, indent=0, title=""):
    ability_phase_details = read_to_dict(TWDBReader("special_ability_phases_tables"), "id")
    ability_phase_stats = read_to_dict_of_lists(TWDBReader("special_ability_phase_stat_effects_tables"), "phase")
    ability_phase_attrs = read_to_dict_of_lists(TWDBReader("special_ability_phase_attribute_effects_tables"), "phase")

    result = ""
    details = ability_phase_details[phase_id]
    unbreakable = "unbreakable " if details["unbreakable"] == "true" else ""
    cant_move = "cant_move " if details["cant_move"] == "true" else ""
    freeze_fatigue = "freeze_fatigue " if details["freeze_fatigue"] == "true" else ""
    fatigue_change_ratio = "fatigue_change_ratio: " + num_str(details["fatigue_change_ratio"]) + " " if details["fatigue_change_ratio"] != "0.0" else ""
    duration = "(" + num_str(details["duration"]) + "s) " if details["duration"] != "-1.0" else ""
    col = "yellow"
    if details["effect_type"] == "positive":
        col = "green"
    elif details["effect_type"] == "negative":
        col = "red"
    replenish_ammo = "replenish_ammo: " + num_str(details["replenish_ammo"]) + " " if details["replenish_ammo"] != "0.0" else ""
    recharge_time = "recharge_time: " + num_str(details["recharge_time"]) + " " if details["recharge_time"] != "-1.0" else ""
    mana_regen_mod = "mana_recharge_mod: " + num_str(details["mana_regen_mod"]) + " " if details["mana_regen_mod"] != "0.0" else ""
    mana_max_depletion_mod = "mana_reserves_mod: " + num_str(details["mana_max_depletion_mod"]) + " " if details["mana_max_depletion_mod"] != "0.0" else ""
    aura_range_mod = "inspiration_range_mod: " + num_str(details["inspiration_aura_range_mod"]) + " " if details["inspiration_aura_range_mod"] != "0.0" else ""
    ability_recharge_change = "reduce_current_cooldowns: " + num_str(details["ability_recharge_change"]) + " " if details["ability_recharge_change"] != "0.0" else ""
    result += indent_str(indent) + title + "[[col:" + col + "]] " + duration + replenish_ammo + unbreakable + mana_regen_mod + mana_max_depletion_mod + cant_move + freeze_fatigue + fatigue_change_ratio + aura_range_mod + ability_recharge_change + recharge_time + "[[/col]]" + "\\\\n"
    # affects_allies + affects_enemies +
    if int(details["heal_amount"]) != 0:
        resurrect = "(or resurrect if full hp) " if details["resurrect"] == "true" else ""
        result += indent_str(indent + 2) + "heal each entity " + resurrect + "by " + stat_str(details["heal_amount"]) + " every " + stat_str(details["hp_change_frequency"] + "s") + "\\\\n"

    if int(details["damage_amount"]) != 0:
        up_to = "up to " + stat_str(details["max_damaged_entities"]) + " " if int(details["max_damaged_entities"]) >= 0 else ""
        chance = "chance (" + stat_str(float(details["damage_chance"]) * 100) + "%) to " if float(details["damage_chance"]) != 1.0 else ""
        result += indent_str(indent + 2) + chance + "damage " + up_to + "entities, each by: " + ability_damage_stat(details["damage_amount"], details["imbue_ignition"], details["imbue_magical"]) + " every " + stat_str(details["hp_change_frequency"] + "s") + "\\\\n"

    if phase_id in ability_phase_stats:
        result += indent_str(indent + 2) + "stats:" + "\\\\n"
        effects = ability_phase_stats[phase_id]

        for effect in effects:
            how = "*" if effect["how"] == "mult" else '+'
            if how == '+' and float(effect["value"]) < 0:
                how = ""
            result += indent_str(indent + 2) + effect["stat"] + " " + how + stat_str(round(float(effect["value"]), 2)) + "\\\\n"
    if phase_id in ability_phase_attrs:
        attrs = ability_phase_attrs[phase_id]
        result += indent_str(indent + 2) + "attributes: "
        for attr in attrs:
            result += stat_str(attr["attribute"]) + " "
        result += "\\\\n"
    if details["imbue_contact"] != "":
        result += ability_phase_details_stats(details["imbue_contact"], indent + 2, "imbue_contact")
    return result


def positive_str(stat, indent=0):
    return indent_str(indent) + "[[col:green]]" + num_str(stat) + "[[/col]]"


def negative_str(stat, indent=0):
    return indent_str(indent) + "[[col:red]]" + num_str(stat) + "[[/col]]"


def indent_str(indent):
    return "[[col:red]] [[/col]]" * indent


def smart_str(stat, indent=0, affinity=1):
    stat_val = float(stat)
    if affinity * stat_val > 0:
        return positive_str(stat, indent)
    if affinity * stat_val < 0:
        return negative_str(stat, indent)
    return stat_str(stat)


def try_int(val):
    try:
        return int(val, 10)
    except ValueError:
        return val


def try_float(val):
    try:
        return float(val)
    except ValueError:
        return val


def num_str(stat):
    conv_stat = try_float(stat)
    if type(conv_stat) != float:
        return str(stat)
    ifstat = round(conv_stat, 0)
    if ifstat == conv_stat:
        return str(int(ifstat))
    return str(round(conv_stat, 2))


def stat_str(stat):
    return "[[col:yellow]]" + num_str(stat) + "[[/col]]"


def derived_stat_str(stat):
    return "[[col:cooking_ingredients_group_3]]" + num_str(stat) + "[[/col]]"


def named_stat(name, stat, indent=0):
    return indent_str(indent) + name + " " + stat_str(stat) + "\\\\n"


# tags:
# [[img:path]] image
# {{tr:}} - locale? (translation)
# [[col]]
def damage_stat(base, ap, ignition, magic, title="dmg"):
    type_str = ""
    if magic == "true":
        type_str += "[[img:ui/skins/default/modifier_icon_magical.png]][[/img]]"
    if float(ignition) != 0:
        type_str += "[[img:ui/skins/default/modifier_icon_flaming.png]][[/img]]"
    armor_piercing_percent = ""
    if float(base) != 0:
        armor_piercing_percent = "(" + stat_str(num_str(round(float(ap) * 100 / (float(base) + float(ap)), 2)) + "%") + ")"
    return title + ": " + stat_str(base) + "+ap:" + stat_str(ap) + armor_piercing_percent + type_str


def icon(name):
    return "[[img:ui/skins/default/" + name + ".png]][[/img]]"


def icon_res(name):
    return "[[img:ui/campaign ui/effect_bundles/" + name + ".png]][[/img]]"


# explosion:
# detonation_duration, detonation_speed,
# contact_phase_effect -> special_ability_phases
# fuse_distance_from_target - This will activate the explosion n metres from target. If n is greater than the distance to the target, then the explosion will occur instantly when the projectile is activated. To get beyond this, add a min_range to the projectile.
# damage/ap is per entity hit
# detonation_force - This is how much force is applied to determine the result of being hit, for knockbacks, etc.
# fuse_fixed_time - Fixed fuse time in s. -1 means not fixed. Use EITHER fixed fuse time or distance from the target
# affects allies - yes/no
# shrapnel: launches another projectile (projectile_shrapnels, amount is num of projectiles )
def explosion_stats(explosion_row, projectile_types, indent=0):
    projectile_text = ""
    projectile_text += indent_str(indent) + damage_stat(explosion_row["detonation_damage"], explosion_row["detonation_damage_ap"], explosion_row["ignition_amount"], explosion_row["is_magical"], "per_entity_dmg") + "\\\\n"
    projectile_text += named_stat("radius", explosion_row["detonation_radius"], indent)

    shrapnel = read_to_dict(TWDBReader("projectile_shrapnels_tables"))

    if explosion_row["affects_allies"] == "false":
        projectile_text += positive_str("doesn't_affect_allies", indent) + "\\\\n"
    if explosion_row["shrapnel"]:
        shrapnel_row = shrapnel[explosion_row["shrapnel"]]
        projectile_text += named_stat("explosion_shrapnel:", "", indent)
        if shrapnel_row["launch_type"] == "sector":
            projectile_text += named_stat("angle", shrapnel_row["sector_angle"], indent + 2)
        projectile_text += named_stat("amount", shrapnel_row["amount"], indent + 2)
        projectile_text += missile_stats(projectile_types[shrapnel_row["projectile"]], None, projectile_types, indent + 2, False)
    if explosion_row["contact_phase_effect"]:
        projectile_text += ability_phase_details_stats(explosion_row["contact_phase_effect"], indent + 2, "contact effect")
    return projectile_text


# projectile:
# fired_by_mount - If this flag is on (and the firing entity is a macro entity) the mount will fire, rather than the rider
# prefer_central_targets - Prefer entities nearer the center of the target (rather than closest in the firing arc)
# scaling_damage - If damage calculation has to be scaled based on different rules
# shots_per_volley - Usually units shoot 1 shot per volley, but some animations have multiple fire points, such as multi-shot artillery units. Most of the logic isn't aware of this, so this field is for reference for those systems
# can_roll - Can the projectile roll on the ground
# can_bounce - can bounce between targets?
# expire_on_impact - If true, the projectile will expire on impact, and will not stick into, or deflect off the object it hit
# is_beam_launch_burst - Launch beams will attempt to make the VFX match the projectiles' travel, and apply a clipping plane when a projectile hits something, culling the projectiles in front
# expiry_range - If this value is positive it dictates the maximum distance a projectile can travel before it expires
# projectile_penetration - what entity sizes can projectile pass through and how much can penetrate before it stops
# can_target_airborne
# is_magical
# ignition_amount How much do we contribute to setting things on fire? Also, if this value is greater than 0, this is considered a flaming attack
# gravity - Use this value to make projectiles more / less affected by gravity. This is mainly used as a representation of wind resistance so that projectiles can hang in the air. Negative means to use "normal" gravity.
# mass - Mass of the projectile.
# burst_size - Number of shots in a single burst (value of 1 means no burst mode)
# burst_shot_delay - Determines the delay between each shot of the same burst
# can_damage_buildings
# can_damage_vehicles
# shockwave_radius
# muzzle_velocity - This describes the speed the projectile launches at (meters per second). If it is negative, the code will calculate this value based on firing at 45 degrees, hitting at the effective range. Not used when the trajectory is fixed!
# max_elevation - This is the maximum angle that the projectile can be fired at. Generally, you want it high (max 90 degrees), and above 45. Except for special cases (e.g. cannon). Not used when the trajectory is fixed!
# fixed elevation - elevation of fixed trajectory
# projectile_number: ? free projectiles not consuming ammo?
# spread: ?
# collision_radius: ?
# homing_params: steering params for the projectile, increases the chance to hit?
# overhead_stat_effect -> special_ability_phase
# contact_stat_effect -> special_ability_phase
# high_air_resistance
# minimum_range
# trajectory_sight, max_elevation
# category: misc ignores shields
# calibration area, distance (the area in square meter a projectile aims, and the area guaranteed to hit at the calibration_distance range)
def missile_stats(projectile_row, unit, projectile_types, indent, projectiles_explosions, trajectory=True, ):
    projectile_text = ""
    building = " "

    if projectile_row["can_damage_buildings"] == "true":
        building += "@buildings "
    if projectile_row["can_damage_vehicles"] == "true":
        building += "@vehicles "
    if projectile_row["can_target_airborne"] == "true":
        building += "@airborne "
    projectile_text += indent_str(indent) + damage_stat(projectile_row["damage"], projectile_row["ap_damage"], projectile_row["ignition_amount"], projectile_row["is_magical"]) + building + "\\\\n"

    # calibration: distance, area, spread
    volley = ""
    if projectile_row["shots_per_volley"] != "1":
        volley += "shots_per_volley " + stat_str(projectile_row["shots_per_volley"])
    if projectile_row["burst_size"] != "1":
        volley += "shots_per_volley " + stat_str(projectile_row["burst_size"]) + " interval " + stat_str(projectile_row["burst_shot_delay"])
    if projectile_row["projectile_number"] != "1":
        volley += "projectiles_per_shot " + stat_str(projectile_row["projectile_number"])

    central_targets = stat_str("closest_target")
    if projectile_row["prefer_central_targets"] == "false":
        central_targets = stat_str("central_target")

    projectile_text += indent_str(indent) + "calibration: " + "area " + stat_str(projectile_row["calibration_area"]) + " distance " + stat_str(projectile_row["calibration_distance"]) + " prefers " + central_targets + "\\\\n"

    if volley != "":
        projectile_text += indent_str(indent) + volley + "\\\\n"
    if unit is not None:
        projectile_text += named_stat("accuracy", float(projectile_row["marksmanship_bonus"]) + float(unit["accuracy"]), indent)
        reload_time = float(projectile_row["base_reload_time"]) * ((100 - float(unit["accuracy"])) * 0.01)
        projectile_text += indent_str(indent) + "reload: " + "skill " + stat_str(unit["reload"]) + " time " + stat_str(reload_time) + "s (base" + stat_str(projectile_row["base_reload_time"]) + "s)" + "\\\\n"

    category = projectile_row["category"]
    if category == "misc" or category == "artillery":
        category += "(ignores shields)"
    projectile_text += indent_str(indent) + "category: " + stat_str(category) + " spin " + stat_str(projectile_row["spin_type"].replace("_spin", "", 1)) + "\\\\n"
    if projectile_row["minimum_range"] != "0.0":
        projectile_text += named_stat("min_range", projectile_row["minimum_range"], indent)

    impact = ""
    if projectile_row["can_bounce"] == "true":
        impact += "bounce "
    if projectile_row["can_roll"] == "true":
        impact += "roll "
    if projectile_row["shockwave_radius"] != "-1.0":
        impact += "shockwave_radius " + projectile_row["shockwave_radius"]

    if trajectory:
        # sight - celownik
        # fixed - attached to the weapon
        # fixed trajectory != fixed sight?
        # some guide: dual_low_fixed means can use both low and fixed

        # trajectory examples
        # - plagueclaw sight: low max elev: 60, fixed elev 45 vel 67, grav -1, mass 50
        # - warp lightning: sight low, max elevation 50, fixed elev 45 vel 110, spin: none mass: 300 grav 6
        # - poison wind mortar globe: type artillery spin axe, sight fixed, max elevation 56, vel 90 grav -1, mass 25, fixed elev 50
        # - ratling gun: type musket spin none, max elevation 88, vel 120, grav -1, mass 5 fix elev 45
        trajectory = "trajectory:"
        trajectory += stat_str(projectile_row["trajectory_sight"])
        trajectory += " vel " + stat_str(projectile_row["muzzle_velocity"])
        trajectory += " max_angle " + stat_str(projectile_row["max_elevation"])
        trajectory += " fixed_angle " + stat_str(projectile_row["fixed_elevation"])
        trajectory += " mass " + stat_str(projectile_row["mass"])  # affects air resistance and shockwave force, doesn't affect speed/acceleration
        if float(projectile_row["gravity"]) != -1:
            trajectory += " g " + stat_str(projectile_row["gravity"])  # default is 10?, affects fall/rise rate of projectile, maybe air resistance?
        projectile_text += indent_str(indent) + trajectory + "\\\\n"

    if impact != "":
        projectile_text += named_stat("impact", impact, indent)
    if projectile_row["spread"] != "0.0":
        projectile_text += named_stat("spread", projectile_row["spread"], indent)
    if projectile_row["homing_params"] != "":
        projectile_text += named_stat("homing", "true", indent)
    if projectile_row["bonus_v_infantry"] != '0':
        projectile_text += named_stat("bonus vs nonlarge", projectile_row["bonus_v_infantry"], indent)
    if projectile_row["bonus_v_large"] != '0':
        projectile_text += named_stat("bonus_vs_large ", projectile_row["bonus_v_large"], indent)
    # todo: projectile_homing details
    # projectile_scaling_damages - scales damage with somebody's health
    if projectile_row["explosion_type"] != "":
        explosion_row = projectiles_explosions[projectile_row["explosion_type"]]
        projectile_text += named_stat("explosion:", "", indent)
        projectile_text += explosion_stats(explosion_row, projectile_types, indent + 2)
    return projectile_text


# todo: fix slowdown at execution
def melee_weapon_stats(melee_id, indent=0):
    unit_desc = ""
    melee_weapons = read_to_dict(TWDBReader("melee_weapons_tables"))
    melee_row = melee_weapons[melee_id]
    # scaling_damage If damage calculation has to be scaled based on different rules
    # col max targets: Maximum targets damaged by a collision attack. This cap is refreshed by collision_attack_max_targets_cooldown.
    # col max targets cooldown: Each second, this amount of targets will be removed from the max targets list, enabling the collision attacker to hit more targets.
    # weapon_length: Relevant for pikes, cavalry refusal distances and proximity. The latter picks between this and 1m + entity radius, whatever is longer, to determine weapon "reach". Chariot riders use this to check if enemies are within reach.
    # max splash targets Maximum entities to attack per splash attack animation. Note that High Priority targets (main units table) always get treated focussed damage.
    # splash dmg multiplier: Multiplier to knock power in splash attack metadata
    # wallbreaker attribute enables damaging walls in melee
    building = ""
    if int(melee_row["building_damage"]) > 0:
        building = " (building: " + stat_str(melee_row["building_damage"]) + ")"  # what about kv_rules["melee_weapon_building_damage_mult"]?
    unit_desc += indent_str(indent) + damage_stat(melee_row["damage"], melee_row["ap_damage"], melee_row["ignition_amount"], melee_row["is_magical"], "melee_dmg") + building + "\\\\n"
    unit_desc += named_stat("melee_reach", melee_row["weapon_length"], indent)
    total_dmg = int(melee_row["damage"]) + int(melee_row["ap_damage"])
    dp10s = (float(total_dmg) * 10) / float(melee_row["melee_attack_interval"])
    unit_desc += indent_str(indent) + "melee_interval " + stat_str(melee_row["melee_attack_interval"]) + " dp10s " + derived_stat_str(round(dp10s, 0)) + "\\\\n"
    if melee_row["bonus_v_infantry"] != "0":
        unit_desc += named_stat("bonus_v_nonlarge", melee_row["bonus_v_infantry"], indent)
    # never set:stats["bonus_v_cav"] = melee_row["bonus_v_cavalry"]
    if melee_row["bonus_v_large"] != "0":
        unit_desc += named_stat("bonus_v_large", melee_row["bonus_v_large"], indent)
    if melee_row["splash_attack_target_size"] != "":
        unit_desc += named_stat("splash dmg:", "", indent)
        # confirmed by ca: blank means no splash damage
        unit_desc += named_stat("target_size", "<=" + melee_row["splash_attack_target_size"], indent + 2)
        unit_desc += indent_str(indent + 2) + "max_targets " + stat_str(melee_row["splash_attack_max_attacks"]) + " dmg_each " + derived_stat_str(round(total_dmg / float(melee_row["splash_attack_max_attacks"]), 0)) + "\\\\n"
        if float(melee_row["splash_attack_power_multiplier"]) != 1.0:
            unit_desc += named_stat("knockback mult", round(float(melee_row["splash_attack_power_multiplier"]), 1), indent + 2)
    if melee_row["collision_attack_max_targets"] != "0":
        unit_desc += indent_str(indent) + " collision: max targets " + stat_str(melee_row["collision_attack_max_targets"]) + " recharge_per_sec " + stat_str(melee_row["collision_attack_max_targets_cooldown"]) + "\\\\n"
    return unit_desc


def missile_weapon_stats(missile_weapon, unit, projectile_types, projectiles_explosions, title="ranged", indent=0):
    weapon_projectile = read_column_to_dict(TWDBReader("missile_weapons_tables"), "key", "default_projectile")
    weapon_secondary_ammo = read_column_to_dict(TWDBReader("missile_weapons_tables"), "key", "use_secondary_ammo_pool")

    # weapon additional projectiles
    weapon_alt_projectile = read_column_to_dict_of_lists(TWDBReader("missile_weapons_to_projectiles_tables"), "missile_weapon", "projectile")

    projectile_text = ""
    projectile_id = weapon_projectile[missile_weapon]
    name = ""
    if weapon_secondary_ammo[missile_weapon] == "true":
        name = "(secondary ammo)"
    projectile_text += indent_str(indent) + title + name + ":" + "\\\\n"
    projectile_row = projectile_types[projectile_id]
    projectile_text += missile_stats(projectile_row, unit, projectile_types, projectiles_explosions, indent + 2)
    if missile_weapon in weapon_alt_projectile:
        for alt_projectile_id in weapon_alt_projectile[missile_weapon]:
            alt_projectile_row = projectile_types[alt_projectile_id]
            name = alt_projectile_row["shot_type"].split("_")[-1]
            if name == "default":
                name = alt_projectile_id
            if weapon_secondary_ammo[missile_weapon] == "true":
                name += "(secondary ammo)"
            projectile_text += indent_str(indent) + title + " (" + name + "):" + "\\\\n"
            projectile_text += missile_stats(alt_projectile_row, unit, projectile_types, projectiles_explosions, indent + 2)
    return projectile_text


# missile_weapon_junctions and effect_bonus_value_missile_weapon_junctions_tables - alternative projectile weapons unlocked in campaign
#  - here I add a dummy ability that shows up when the custom weapon effect is enabled in campaign
#  - example: "the very latest thing" skill of Ikit claw
#  - there are units with alternatives (or multiple) upgrades (grom's cooking gives different weapon types to goblins)
# unit_special_abilities_tables - add a dummy infinite ability with no effects, will not show up in ui without this
# unit_abilities_tables - add a passive ability for every weapon effect
# unit_abilities__.loc -  add both name and tooltip entry for every added ability
# effect_bonus_value_unit_ability_junctions_tables - copy every entry from effect_bonus_value_missile_weapon_junctions_tables, replace missile weapon id with new ability key
def get_missile_weapon_junctions():
    missile_weapon_junctions = {}
    missile_weapon_for_junction = {}
    with TWDBReader("unit_missile_weapon_junctions_tables") as db_reader:
        for row in db_reader.rows_iter:
            key = "unit"
            if row[key] not in missile_weapon_junctions:
                missile_weapon_junctions[row[key]] = []
            missile_weapon_junctions[row[key]].append(row)
            key = "id"
            missile_weapon_for_junction[row[key]] = row
    return missile_weapon_junctions, missile_weapon_for_junction


# unit ability doesn't have anything interesting
# unit_special_ability uses unit_ability as a key according to dave
# num_uses - charges?
# active time - If this is a projectile then set -1 for active time
# activated projectiles - projectiles table
# target_friends/enemies/ground
# assume_specific_behaviour - special_abilities_behaviour_types (Cantabrian circle, etc.)
# bombardment - projectile_bombardments table
# spawned unit - land_units_table
# vortex: battle_vortexs vortex_key
# wind_up_stance, wind_down_stance -> special_ability_stance_enums
# use_loop_stance - Entities will play a loop locomotion stance
# mana_cost
# min_range - "too close" error?
# initial_recharge, recharge_time, wind_up_time
# passive
# effect_range
# affect_self
# num_effected_friendly_units
# num_effected_enemy_units
# update_targets_every_frame
# clear_current_order
# targetting_aoe -> area_of_effect_displays - This is the area of effect to display when targeting
# passive_aoe -> area_of_effect_displays - This is the area of effect to display when the ability has been ordered but not yet cast (like if a unit has to move there to cast)
# active_aoe -> area_of_effect_displays - This is the area of effect to display when the ability is active (has been cast)
# miscast chance - The unary chance of a miscast occurring
# miscast_explosion -> projectiles_explosions
# target_ground_under_allies
# target_ground_under_enemies
# target_self
# target_intercept_range - ?
# only_affect_owned_units - If it's affecting friendly units, it only affects those in the same army as the owner
# spawn_is_decoy - If spawning a unit the new one will be understood as a decoy of the owner one, the UI will show data for the owning one
# spawn_is_transformation - If spawning a unit will mean the owner unit will be replaced by the spawned one
def unit_abilities_table(unit_ability_loc_writer, ability_details, projectile_types, missile_weapon_for_junction, projectiles_explosions):
    unit_ability_writer = TWDBReader("unit_abilities_tables").data_into_writer()

    # tracks sets already populated
    unit_set = read_to_dict(TWDBReader("unit_sets_tables"))
    unit_set_writer = TWDBReader("unit_sets_tables").data_into_writer()

    unit_set_to_unit_writer = TWDBReader("unit_set_to_unit_junctions_tables").data_into_writer()
    unit_set_ability_writer = TWDBReader("unit_set_unit_ability_junctions_tables").data_into_writer()

    effect_bonus_ability_writer = TWDBReader("effect_bonus_value_unit_set_unit_ability_junctions_tables").data_into_writer()
    effect_bonus_missile_junctions = read_to_dict_of_lists(TWDBReader("effect_bonus_value_missile_weapon_junctions_tables"), "effect")

    ability_proto_map = {"icon_name": "ranged_weapon_stat",
                         "is_hidden_in_ui": "false",
                         "is_hidden_in_ui_for_enemy": "false",
                         "is_unit_upgrade": "false",
                         "key": "ikit_claw_missile_tooltip",
                         "requires_effect_enabling": "true",
                         "source_type": "unit",
                         "type": "wh_type_augment",
                         "uniqueness": "wh_main_anc_group_common"}

    ability_details_proto_map = {"active_time": "-1",
                                 "additional_melee_cp": "0",
                                 "additional_missile_cp": "0",
                                 "affect_self": "false",
                                 "clear_current_order": "false",
                                 "effect_range": "0",
                                 "initial_recharge": "-1",
                                 "key": "ikit_claw_missile_tooltip",
                                 "mana_cost": "0",
                                 "min_range": "0",
                                 "miscast_chance": "0",
                                 "miscast_global_bonus": "false",
                                 "num_effected_enemy_units": "0",
                                 "num_effected_friendly_units": "0",
                                 "num_uses": "-1",
                                 "only_affect_owned_units": "false",
                                 "passive": "true",
                                 "recharge_time": "-1",
                                 "shared_recharge_time": "-1",
                                 "spawn_is_decoy": "false",
                                 "spawn_is_transformation": "false",
                                 "target_enemies": "false",
                                 "target_friends": "false",
                                 "target_ground": "false",
                                 "target_ground_under_allies": "false",
                                 "target_ground_under_enemies": "false",
                                 "target_intercept_range": "0",
                                 "target_self": "true",
                                 "unique_id": "17224802351",
                                 "update_targets_every_frame": "0",
                                 "use_loop_stance": "false",
                                 "voiceover_state": "vo_battle_special_ability_generic_response",
                                 "wind_up_time": "0"}

    ability_details_writer = TWDBReader("unit_special_abilities_tables").data_into_writer()

    for effect_id in effect_bonus_missile_junctions:
        ability_details_max_id = 0
        for key in ability_details:
            row = ability_details[key]
            new_id = int(row["unique_id"])
            if new_id > ability_details_max_id:
                ability_details_max_id = new_id

        effect_rows = effect_bonus_missile_junctions[effect_id]
        for effect_row in effect_rows:
            ability_id = effect_id + "_" + effect_row["missile_weapon_junction"] + "_stats"
            weapon_junction = missile_weapon_for_junction[effect_row["missile_weapon_junction"]]
            weapon_id = weapon_junction["missile_weapon"]

            ability_name_row = unit_ability_loc_writer.make_row()
            ability_name_row["key"] = "unit_abilities_onscreen_name_" + ability_id

            ability_name_row["text"] = weapon_id.split("_", 2)[2]
            ability_name_row["tooltip"] = "true"
            unit_ability_loc_writer.new_rows.append(ability_name_row)
            ability_text_row = unit_ability_loc_writer.make_row()
            ability_text_row["key"] = "unit_abilities_tooltip_text_" + ability_id
            ability_text_row["text"] = missile_weapon_stats(weapon_id, None, projectile_types, projectiles_explosions)
            ability_text_row["tooltip"] = "true"
            unit_ability_loc_writer.new_rows.append(ability_text_row)
            ability_row = unit_ability_writer.make_row(ability_proto_map)
            ability_row["key"] = ability_id
            unit_ability_writer.new_rows.append(ability_row)

            ability_detail_row = ability_details_writer.make_row(ability_details_proto_map)
            ability_detail_row["key"] = ability_id
            ability_details_max_id = ability_details_max_id + 1
            ability_detail_row["unique_id"] = str(ability_details_max_id)
            ability_details_writer.new_rows.append(ability_detail_row)

            unit_id = weapon_junction["unit"]
            unit_set_id = unit_id
            if unit_set_id not in unit_set:
                unit_set_row = unit_set_writer.make_row()
                unit_set_row["key"] = unit_set_id
                unit_set_row["use_unit_exp_level_range"] = "false"
                unit_set_row["min_unit_exp_level_inclusive"] = "-1"
                unit_set_row["max_unit_exp_level_inclusive"] = "-1"
                unit_set_row["special_category"] = ""
                unit_set[unit_set_id] = unit_set_row
                unit_set_writer.new_rows.append(unit_set_row)

                unit_set_to_unit_row = unit_set_to_unit_writer.make_row()
                unit_set_to_unit_row["unit_set"] = unit_set_id
                unit_set_to_unit_row["unit_record"] = unit_id
                unit_set_to_unit_row["unit_caste"] = ""
                unit_set_to_unit_row["unit_category"] = ""
                unit_set_to_unit_row["unit_class"] = ""
                unit_set_to_unit_row["exclude"] = "false"
                unit_set_to_unit_writer.new_rows.append(unit_set_to_unit_row)

            unit_set_ability_id = unit_set_id + "_" + ability_id
            unit_set_ability_row = unit_set_ability_writer.make_row()
            unit_set_ability_row["key"] = unit_set_ability_id
            unit_set_ability_row["unit_set"] = unit_set_id
            unit_set_ability_row["unit_ability"] = ability_id
            unit_set_ability_writer.new_rows.append(unit_set_ability_row)

            effect_bonus_ability_row = effect_bonus_ability_writer.make_row()
            effect_bonus_ability_row["effect"] = effect_id
            effect_bonus_ability_row["bonus_value_id"] = effect_row["bonus_value_id"]
            effect_bonus_ability_row["unit_set_ability"] = unit_set_ability_id
            effect_bonus_ability_writer.new_rows.append(effect_bonus_ability_row)

    unit_ability_writer.write()
    ability_details_writer.write()
    unit_set_writer.write()
    unit_set_to_unit_writer.write()
    unit_set_ability_writer.write()
    effect_bonus_ability_writer.write()


def main_units_tables(missile_weapon_junctions, projectile_types, projectiles_explosions):
    land_unit_to_spawn_info = {}

    land_units = read_to_dict(TWDBReader("land_units_tables"))
    battle_entities = read_to_dict(TWDBReader("battle_entities_tables"))

    # only used by battle personalities and officers
    battle_entity_stats = read_to_dict(TWDBReader("battle_entity_stats_tables"))

    land_units_officers = read_to_dict(TWDBReader("land_units_officers_tables"))
    battle_personalities = read_to_dict(TWDBReader("battle_personalities_tables"))
    personality_group = read_column_to_dict_of_lists(TWDBReader("land_units_additional_personalities_groups_junctions_tables"), "group", "battle_personality")

    bullet_point_enums_writer = TWDBReader("ui_unit_bullet_point_enums_tables").data_into_writer()
    bullet_point_override_writer = TWDBReader("ui_unit_bullet_point_unit_overrides_tables").data_into_writer()

    # bullet point descriptions
    bullet_points_loc_writer = TWLocDBReader("ui_unit_bullet_point_enums").data_into_writer()

    articulated_entity = read_column_to_dict(TWDBReader("land_unit_articulated_vehicles_tables"), "key", "articulated_entity")
    mount_entity = read_column_to_dict(TWDBReader("mounts_tables"), "key", "entity")

    shield_types = read_column_to_dict(TWDBReader("unit_shield_types_tables"), "key", "missile_block_chance")
    ground_type_stats = read_to_dict_of_dicts_of_lists(TWDBReader("ground_type_to_stat_effects_tables"), "affected_group", "ground_type")

    engine_weapon = {}
    engine_entity = {}
    engine_mounted = {}
    with TWDBReader("battlefield_engines_tables") as db_reader:
        for row in db_reader.rows_iter:
            engine_weapon[row["key"]] = row["missile_weapon"]
            engine_entity[row["key"]] = row["battle_entity"]
            engine_mounted[row["key"]] = "No_Crew" in row["engine_type"]

    unit_names = {}
    with TWLocDBReader("land_units") as db_reader:
        for row in db_reader.rows_iter:
            key = row["key"]
            if "land_units_onscreen_name_" in key:
                key = key.replace("land_units_onscreen_name_", "", 1)
                unit_names[key] = row["text"]

    with TWDBReader("main_units_tables") as db_reader:
        for row in db_reader.rows_iter:
            main_unit_entry = row
            # main_unit:
            # caste: Among other usages, caste allows the overriding of UI stat bar max values
            # is_high_threat: High threat units override the entity threshold checks of melee reactions. If they run into or attack a unit, the unit will instantly react, even if less than 25% of their entities are affected.
            # unit_scaling: Determines if the number of men / artillery pieces in this unit should be scaled with the gfx unit size setting (true) or not (false)
            # mount: mount on campaign map
            # tier: unit tier
            # melee_cp: Base Melee Combat Potential of this unit. Must be >= 0.0 or the game will crash on startup. This value is modified (increased) by other factors such as Rank and equipped Abilities / Items. Reduced by 20% for missile cavalry.
            # can_siege - If true, can attack the turn a settlement is besieged - do not need to wait to build siege equipment on the campaign map
            # is_monstrous - Is this unit regarded as monstrous for voiceover?
            # vo_xx - voiceover
            # multiplayer_qb_cap - Multiplayer cap for quest battles, requested by Alisdair
            unit = land_units[main_unit_entry["land_unit"]]

            stats = {}
            indent = 0
            unit_desc = ""
            # looks like num of non-autonomous-rider officers needs to be subtracted to have accurate numbers (based on bloodwrack_shrine in dark elf roster, ikit_claw_doomwheel, etc.)
            num_men = int(main_unit_entry["num_men"])

            if unit["campaign_action_points"] != "2100":
                stats["campaign_range"] = unit["campaign_action_points"]
            if unit["hiding_scalar"] != "1.0":
                stats["hiding_scalar"] = unit["hiding_scalar"]
            if unit["shield"] != "none":
                stats["missile_block"] = shield_types[unit["shield"]] + "%"
            stats["capture_power"] = unit["capture_power"]  # also apparently dead vehicles have capture power?
            # land_unit
            # todo: spot dist tree/ spot dist scrub/
            # hiding scalar -This affects the range that the unit can be spotted at, less than 1 makes it longer, greater than 1 shorter. So 1.5 would increase the spotters' range by +50%
            # sync locomotion - undead sync anim
            # training level: deprecated
            # visibility_spotting_range_min/max
            # attribute group - lists attributes
            if main_unit_entry["is_high_threat"] == "true":
                unit_desc += stat_str("high_threat (focuses enemy attack and splash damage)") + "\\\\n"

            entity = battle_entities[unit["man_entity"]]
            # entity column doc
            # todo: figure out which entity are these stats taken from? mount/engine/man?
            # combat_reaction_radius: Radius at which entity will trigger combat with nearby enemy
            # fly_speed: Speed of the entity when in the air (as opposed to moving on the ground)
            # fly_charge_speed
            # fire_arc_close? - like the angle of the fire cone aiming cone for facing the target, can be seen by simple hover, not needed in stats?
            # projectile_intersection_radius_ratio: Ratio of the radius to use for projectile intersections (usually < 1)
            # projectile_penetration_resistance: Added to the projectile penetration counter. A higher number means this entity can stop projectiles more easily.
            # projectile_penetration_speed_change: Ratio of projectile speed retained when it penetrates this entity.
            # min_tracking_ratio: Minimum ratio of move speed that an entity can slow down for formed movement
            # can_dismember: can be dismembered
            # jump_attack_chance: percentage chance of a jump attack
            # dealt_collision_knocked_flying_threshold_multiplier: Multiplier for the collision speed delta threshold to apply to the victim of the collision
            # dealt_collision_knocked_down_threshold_multiplier: Multiplier for the collision speed delta threshold to apply to the victim of the collision
            # dealt_collision_knocked_back_threshold_multiplier: Multiplier for the collision speed delta threshold to apply to the victim of the collision
            # can_cast_projectile: does this entity cast a projectile spell

            if entity["hit_reactions_ignore_chance"] != "0":
                stats["hit_reactions_ignore"] = entity["hit_reactions_ignore_chance"] + "%"

            if entity["knock_interrupts_ignore_chance"] != "0":
                stats["knock_interrupts_ignore"] = entity["knock_interrupts_ignore_chance"] + "%"

            # officer entities, weapons and missiles - sometimes there's no primary weapon/missile, but officers have one and that's shown on the stat screen
            # example: Ikit variant doomwheel
            # officers->land units officers tables, land_units_officers(additional_personalities) -> land_units_additional_personalities_groups_junctions -> battle_personalities(battle_entity_stats, also battle_entity) -> battle_entity_stats
            # also land_units_officers(officers) -> battle_personalities(battle_entity_stats, also battle_entity) -> battle_entity_stats,
            if unit["officers"] != "":
                officer_row = land_units_officers[unit["officers"]]
                unit_personalities = []
                if officer_row["officer_1"] != "":  # officer2 is deprecated
                    unit_personalities.append(officer_row["officer_1"])
                if officer_row["additional_personalities"] != "":
                    additional = personality_group[officer_row["additional_personalities"]]
                    unit_personalities.extend(additional)

            support_entities = []
            support_melee_weapons = []
            melee_weapons_set = set()
            support_ranged_weapons = []
            ranged_weapons_set = set()

            if unit["primary_melee_weapon"] != "":
                melee_weapons_set.add(unit["primary_melee_weapon"])

            if unit["primary_missile_weapon"] != "":
                ranged_weapons_set.add(unit["primary_missile_weapon"])

            if unit["engine"] != "":
                if engine_weapon[unit["engine"]] != "":
                    ranged_weapons_set.add(engine_weapon[unit["engine"]])

            for personality_id in unit_personalities:
                unit_personality = battle_personalities[personality_id]
                entity_personality_id = unit_personality["battle_entity"]
                if "autonomous_rider_hero" != "true":
                    # support entities (officers) that aren't the autonomous rider entity count towards mass and health
                    # they don't count towards speed
                    support_entities.append(entity_personality_id)
                    num_men -= 1
                else:
                    # main entities should always be the same as main entity and don't count towards mass/health
                    if entity_personality_id != unit["man_entity"]:
                        print("main entity conflict:" + entity_personality_id)
                    stat_id = unit_personality["battle_entity_stats"]
                    if stat_id != "":
                        stats = battle_entity_stats[stat_id]
                        # autonomous rider hero personalities sometimes have a weapon even if missing in land_unit_table (example: Ikit claw doomwheel)
                        melee_id = stats["primary_melee_weapon"]
                        if melee_id != "":
                            melee_weapons_set.add(melee_id)
                        missile_id = stats["primary_missile_weapon"]
                        if missile_id != "":
                            ranged_weapons_set.add(missile_id)

            charge_speed = float(entity["charge_speed"]) * 10
            speed = float(entity["run_speed"]) * 10
            fly_speed = float(entity["fly_speed"]) * 10
            fly_charge_speed = float(entity["flying_charge_speed"]) * 10
            accel = float(entity["acceleration"])
            size = entity["size"]
            if unit["engine"] != "":
                # speed characteristics are always overridden by engine and mount, even if engine is engine_mounted == false (example: catapult), verified by comparing stats
                engine = battle_entities[engine_entity[unit["engine"]]]
                charge_speed = float(engine["charge_speed"]) * 10
                accel = float(engine["acceleration"])
                speed = float(engine["run_speed"]) * 10
                fly_speed = float(engine["fly_speed"]) * 10
                fly_charge_speed = float(engine["flying_charge_speed"]) * 10
                support_entities.append(engine_entity[unit["engine"]])
                # only override size when engine is used as a mount (i.e. it's something you drive, not push), verified by comparing stats; overrides mount, verified by comparing stats
                if engine_mounted[unit["engine"]]:
                    size = engine["size"]
            if unit["articulated_record"] != "":  # never without an engine
                support_entities.append(articulated_entity[unit["articulated_record"]])
            if unit["mount"] != "":
                mount = battle_entities[mount_entity[unit["mount"]]]
                # both engine and mount present - always chariots
                # verified, the mount has higher priority than engine when it comes to determining speed (both increasing and decreasing), by comparing stats of units where speed of mount < or >  engine
                charge_speed = float(mount["charge_speed"]) * 10
                accel = float(mount["acceleration"])
                speed = float(mount["run_speed"]) * 10
                fly_speed = float(mount["fly_speed"]) * 10
                fly_charge_speed = float(mount["flying_charge_speed"]) * 10
                support_entities.append(mount_entity[unit["mount"]])
                # verified that chariots use the size of the chariot, not the mount; skip overriding
                if not (unit["engine"] != "" and engine_mounted[unit["engine"]]):
                    size = engine["size"]

            health = int(entity["hit_points"]) + int(unit["bonus_hit_points"])
            mass = float(entity["mass"])

            for support_id in support_entities:
                support_entity = battle_entities[support_id]
                mass += float(support_entity["mass"])
                health += int(support_entity["hit_points"])

            stats["health (ultra scale)"] = num_str(health)
            stats["mass"] = num_str(mass)
            target_size = "nonlarge" if size == "small" else "large"
            stats["size"] = size + " (" + target_size + " target)"

            if len(melee_weapons_set) > 1:
                print("melee weapon conflict (land unit):" + unit["key"])
            for melee_id in melee_weapons_set:
                unit_desc += melee_weapon_stats(melee_id)

            unit_desc += indent_str(indent) + "run_speed " + stat_str(speed) + " charge " + stat_str(charge_speed) + " acceleration " + stat_str(accel * 10) + "\\\\n"
            if fly_speed != 0:
                unit_desc += indent_str(indent) + "fly_speed " + stat_str(fly_speed) + " charge " + stat_str(fly_charge_speed) + "\\\\n"

            # land_unit -> ground_stat_effect_group -> ground_type_stat_effects
            if unit["ground_stat_effect_group"] != "" and unit["ground_stat_effect_group"] in ground_type_stats:
                ground_types = ground_type_stats[unit["ground_stat_effect_group"]]

                unit_desc += "ground effects (negatives are cancelled by strider attr): " + "\\\\n"
                for gtype in ground_types:
                    stat_desc = gtype + ": "
                    for stat_row in ground_types[gtype]:
                        stat_desc += stat_row["affected_stat"].replace("scalar_", "", 1).replace("stat_", "", 1) + " * " + stat_str(stat_row["multiplier"]) + " "
                    unit_desc += indent_str(indent + 2) + stat_desc + "\\\\n"

            # ammo is the number of full volleys (real ammo is num volleys * num people)
            if int(unit["secondary_ammo"]) != 0:
                stats["secondary_ammo"] = unit["secondary_ammo"]

            for stat in stats:
                unit_desc += named_stat(stat, stats[stat], indent)

            if main_unit_entry["unit"] in missile_weapon_junctions:
                unit_desc += stat_str("ranged_weapon_replacement_available_in_campaign [[img:ui/battle ui/ability_icons/ranged_weapon_stat.png]][[/img]]") + "\\\\n"

            if len(ranged_weapons_set) > 1:
                print("missile weapon conflict (land unit):" + unit["key"])
            for missile_weapon in ranged_weapons_set:
                unit_desc += missile_weapon_stats(missile_weapon, unit, projectile_types, projectiles_explosions, indent=indent)

            for personality_id in unit_personalities:
                unit_personality = battle_personalities[personality_id]
                stat_id = unit_personality["battle_entity_stats"]
                if stat_id != "":
                    stats = battle_entity_stats[stat_id]
                    melee_id = stats["primary_melee_weapon"]
                    if melee_id != "" and melee_id not in melee_weapons_set:
                        melee_weapons_set.add(melee_id)
                        support_melee_weapons.append(melee_id)

                    missile_id = stats["primary_missile_weapon"]
                    if missile_id != "" and missile_id not in ranged_weapons_set:
                        ranged_weapons_set.add(missile_id)
                        support_ranged_weapons.append(missile_id)

            for melee_id in support_melee_weapons:
                unit_desc += "melee_support:" + "\\\\n"
                unit_desc += melee_weapon_stats(melee_id, 2)

            for missile_id in support_ranged_weapons:
                unit_desc += missile_weapon_stats(missile_id, None, projectile_types, "ranged_support")

            spawn_info = unit_names[main_unit_entry["land_unit"]] + " (" + main_unit_entry["caste"] + ", tier " + main_unit_entry["tier"] + " men " + num_str(num_men) + ")"
            land_unit_to_spawn_info[main_unit_entry["land_unit"]] = spawn_info

            # store
            main_unit_id = main_unit_entry["unit"]
            new_bullet_id = main_unit_id + "_stats"
            new_bullet_enum = bullet_point_enums_writer.proto_row()
            new_bullet_enum["key"] = new_bullet_id
            new_bullet_enum["state"] = "very_positive"
            new_bullet_enum["sort_order"] = "0"
            bullet_point_enums_writer.new_rows.append(new_bullet_enum)
            new_override = bullet_point_override_writer.proto_row()
            new_override["unit_key"] = main_unit_id
            new_override["bullet_point"] = new_bullet_id
            bullet_point_override_writer.new_rows.append(new_override)

            bullet_name_id = "ui_unit_bullet_point_enums_onscreen_name_" + new_bullet_id
            bullet_tooltip_id = "ui_unit_bullet_point_enums_tooltip_" + new_bullet_id

            bullet_point_name_loc = bullet_points_loc_writer.proto_row()
            bullet_point_name_loc["key"] = bullet_name_id
            bullet_point_name_loc["text"] = "Hover for Base Stats"
            bullet_points_loc_writer.new_rows.append(bullet_point_name_loc)

            bullet_point_tooltip_loc = bullet_points_loc_writer.proto_row()
            bullet_point_tooltip_loc["key"] = bullet_tooltip_id
            bullet_point_tooltip_loc["text"] = unit_desc
            bullet_points_loc_writer.new_rows.append(bullet_point_tooltip_loc)

    bullet_point_enums_writer.write()
    bullet_point_override_writer.write()
    bullet_points_loc_writer.write()

    return land_unit_to_spawn_info


# projectile bombardment - done
# num_projectiles The total number of projectiles that will spawn. Their arrival times are random, within the times specified
# start_time is the minimum time (seconds) that must pass before a projectile can appear
# arrival_window The time (seconds) duration that any of the projectiles can appear
# radius_spread How far away from the target this can theoretically land
# launch_source The suggested starting location of the bombardment
# launch_height_(underground)

# battle vortices - done
# duration
# damage/damage_ap
# expansion_speed
# start_radius
# goal_radius
# movement_speed - in metres / second
# move_change_freq
# change_max_angle
# contact_effect -> special_ability_phases
# height_off_ground
# infinite_height
# ignition_amount
# is_magical
# detonation_force
# launch_source -> battle vortex_launch_sources
# delay: We do spawn this at the same time as usual, but we wait this time to cause damage / move / collide, etc.
# num_vortexes - num of vortexes spawned
# affects_allies
# launch_source_offset- distance from launch_source
# delay_between_vortexes

# todo: fix major slowdown in execution
def ability_descriptions(unit_ability_loc_reader, unit_ability_loc_writer, projectile_types, ability_details, land_unit_to_spawn_info, projectiles_explosions):
    bombardments = read_to_dict(TWDBReader("projectile_bombardments_tables"), "bombardment_key")
    vortices = read_to_dict(TWDBReader("battle_vortexs_tables"), "vortex_key")
    ability_phases = read_column_to_dict_of_lists(TWDBReader("special_ability_to_special_ability_phase_junctions_tables"), "special_ability", "phase")

    with unit_ability_loc_reader as db_reader:
        for new_row in db_reader.rows_iter:
            unit_ability_loc_writer.new_rows.append(new_row)
            if "unit_abilities_tooltip_text_" in new_row["key"]:
                description_id = new_row["key"].replace("unit_abilities_tooltip_text_", "", 1)
                result = "\\\\n" + "\\\\n"

                if description_id in ability_details:
                    ability = ability_details[description_id]

                    if ability["passive"] == "false":
                        result += named_stat("cast_time", ability["wind_up_time"])
                        result += named_stat("active_time", ability["active_time"])
                        initial_recharge = ""
                        if float(ability["initial_recharge"]) > 0:
                            initial_recharge = ", initial " + ability["initial_recharge"]
                        result += named_stat("recharge_time", ability["recharge_time"] + initial_recharge)
                        if float(ability["min_range"]) > 0:
                            result += named_stat("min_range", ability["min_range"] + initial_recharge)

                    if int(ability["num_effected_friendly_units"]) > 0:
                        result += named_stat("affected_friendly_units", ability["num_effected_friendly_units"])
                    if int(ability["num_effected_enemy_units"]) > 0:
                        result += named_stat("affected_enemy_units", ability["num_effected_enemy_units"])
                    if ability["only_affect_owned_units"] == "true":
                        result += named_stat("only_affect_owned_units", ability["only_affect_owned_units"])
                    if ability["update_targets_every_frame"] == "true":
                        result += named_stat("update_targets_every_frame", ability["update_targets_every_frame"])

                    if ability["assume_specific_behaviour"]:
                        result += named_stat("behaviour", ability["assume_specific_behaviour"])

                    if ability["bombardment"] != "":
                        bombardment = bombardments[ability["bombardment"]]
                        result += "Bombardment:" + "\\\\n"
                        result += named_stat("num_bombs", bombardment["num_projectiles"], 2)
                        result += named_stat("radius_spread", bombardment["radius_spread"], 2)
                        result += named_stat("launch_source", bombardment["launch_source"], 2)
                        result += named_stat("launch_height", bombardment["launch_height"], 2)
                        result += named_stat("start_time", bombardment["start_time"], 2)
                        result += named_stat("arrival_window", bombardment["arrival_window"], 2)
                        bomb_projectile = projectile_types[bombardment["projectile_type"]]
                        result += missile_stats(bomb_projectile, None, projectile_types, projectiles_explosions, 2)
                        result += "\\\\n"
                    if ability["activated_projectile"] != "":
                        result += "Projectile:"
                        projectile = projectile_types[ability["activated_projectile"]]
                        result += missile_stats(projectile, None, projectile_types, projectiles_explosions, 2)
                        result += "\\\\n"
                    if ability["vortex"] != "":
                        result += "Vortex:" + "\\\\n"
                        indent = 2
                        vortex = vortices[ability["vortex"]]
                        if vortex["num_vortexes"] != "1":
                            result += indent_str(indent) + " vortex count: " + stat_str(vortex["num_vortexes"]) + " vortexes " + stat_str(vortex["delay_between_vortexes"]) + "s delay between" + "\\\\n"
                        if vortex["start_radius"] == vortex["goal_radius"]:
                            radius = stat_str(vortex["start_radius"])
                        else:
                            radius = "start " + stat_str(vortex["start_radius"]) + " goal " + stat_str(vortex["goal_radius"]) + " expansion speed " + stat_str(vortex["expansion_speed"])
                        result += indent_str(indent) + "radius: " + radius + "\\\\n"
                        result += indent_str(indent) + damage_stat(vortex["damage"], vortex["damage_ap"], vortex["ignition_amount"], vortex["is_magical"]) + "\\\\n"
                        result += named_stat("detonation_force", vortex["detonation_force"], indent)
                        result += named_stat("initial_delay", vortex["delay"], indent)
                        result += named_stat("duration", vortex["duration"], indent)
                        if vortex["building_collision"] == "2.expire":
                            result += indent_str(indent) + stat_str("building collision expires vortex") + "\\\\n"
                        result += named_stat("launch_source", vortex["launch_source"], indent)
                        if vortex["launch_source_offset"] != "0.0":
                            result += named_stat("launch_source_offset", vortex["launch_source_offset"], indent)
                        if float(vortex["movement_speed"]) == 0:
                            path = "stationary"
                        elif vortex["change_max_angle"] == "0":
                            path = "straight line, speed " + stat_str(vortex["movement_speed"])
                        else:
                            path = "angle changes by " + stat_str("0-" + num_str(vortex["change_max_angle"])) + " every " + stat_str(vortex["move_change_freq"]) + ", speed " + stat_str(vortex["movement_speed"])
                        result += indent_str(indent) + "path: " + path + "\\\\n"
                        if vortex["affects_allies"] == "false":
                            result += positive_str("doesn't_affect_allies", indent) + "\\\\n"
                        if vortex["contact_effect"] != "":
                            result += ability_phase_details_stats(phase_id, indent, "contact effect")
                    if ability["spawned_unit"] != "":
                        result += "Spawn: "
                        if ability["spawn_is_decoy"] == "true":
                            result += "(decoy) "
                        if ability["spawn_is_transformation"] == "true":
                            result += "(transform) "
                        result += land_unit_to_spawn_info[ability["spawned_unit"]]
                        result += "\\\\n"
                    if ability["miscast_explosion"] != "":
                        result += "Miscast explosion (chance:" + stat_str(float(ability["miscast_chance"]) * 100) + "%):"
                        explosion_row = projectiles_explosions[ability["miscast_explosion"]]
                        result += explosion_stats(explosion_row, projectile_types, 2)
                        result += "\\\\n"
                if description_id in ability_phases:
                    result += "Phases:" + "\\\\n"
                    phases = ability_phases[description_id]
                    i = 0
                    for phase_id in phases:
                        i = i + 1
                        result += ability_phase_details_stats(phase_id, 2, num_str(i) + ".")
                new_row["text"] = new_row["text"] + result

    # new unit abilities localization entries
    unit_ability_loc_writer.write()


def get_fatigue_effects(fatigue_order):
    fatigue_effects = {}
    with TWDBReader("unit_fatigue_effects_tables") as db_reader:
        for row in db_reader.rows_iter:
            key = row["fatigue_level"].replace("threshold_", "", 1)
            stat = row["stat"].replace("scalar_", "", 1).replace("stat_", "", 1)
            if key not in fatigue_effects:
                fatigue_effects[key] = {}
            fatigue_effects[key][stat] = row["value"]

    prev_level = {}
    for fatigue_level in fatigue_order:
        for stat in prev_level:
            if stat not in fatigue_effects[fatigue_level]:
                fatigue_effects[fatigue_level][stat] = prev_level[stat]
        prev_level = fatigue_effects[fatigue_level]

    return fatigue_effects


# good icons:
# calibration_distance: icon_distance_to_target
# missile attack: icon_stat_ranged_damage_base
# missile range: icon_stat_range
# reload time: icon_stat_reload_time
# ammo: icon_stat_ammo
# armour: ui/skins/default/icon_stat_armour
# attack: ui/skins/default/icon_stat_attack
# defence: ui/skins/default/icon_stat_defence
# AP melee: modifier_icon_armour_piercing
# AP ranged: modifier_icon_armour_piercing_ranged
# AP explosive: icon_stat_explosive_armour_piercing_damage
# ui/skins/default/icon_stat_...
# ui/skins/default/modifier_icon_...
# dmg type:
# magical: modifier_icon_magical
# flaming: modifier_icon_flaming
# res type:
# ward save: ui/campaign ui/effect_bundles/resistance_ward_save
# phys res: ui/campaign ui/effect_bundles/resistance_physical
# magic res: ui/campaign ui/effect_bundles/resistance_magic
# ranged res: ui/campaign ui/effect_bundles/resistance_missile
# fire res: ui/campaign ui/effect_bundles/resistance_fire

def stat_descriptions(kv_rules, kv_morale, fatigue_order, fatigue_effects, stat_icons):
    kv_fatigue = read_column_to_dict(TWDBReader("_kv_fatigue_tables"), "key", "value")

    with TWLocDBReader("unit_stat_localisations") as db_reader:
        db_writer = db_reader.make_writer()
        for new_row in db_reader.rows_iter:
            db_writer.new_rows.append(new_row)
            new_text = ""
            key = new_row["key"]

            if key == "unit_stat_localisations_tooltip_text_stat_armour":
                armour_text = "Survivability mechanics: ||"
                armour_text += "Armour blocks a percentage of all non " + icon("modifier_icon_armour_piercing") + "/" + icon("modifier_icon_armour_piercing_ranged") + "/" + icon("icon_stat_explosive_armour_piercing_damage") + " damage:" + '||'
                armour_text += "random from " + icon("icon_stat_armour") + stat_str(float(kv_rules["armour_roll_lower_cap"]) * 100) + "%" + " to " + icon("icon_stat_armour") + stat_str(100) + "% " + '||'
                armour_text += "max 100" + "|| " + '||'
                armour_text += "An attack can be physical OR " + icon("modifier_icon_magical") + ", blocked by " + icon_res("resistance_physical") + " OR " + icon_res("resistance_magic") + '||'
                armour_text += "It may also be " + icon("icon_stat_ranged_damage_base") + " and/or " + icon("modifier_icon_flaming") + ", blocked by " + icon_res("resistance_missile") + " and/or " + icon_res("resistance_fire") + '||'
                armour_text += icon_res("resistance_ward_save") + " is always active" + "|| " + '||'
                armour_text += "All relevant resistances are added up" + '||'
                armour_text += icon_res("resistance_ward_save") + " + " + icon_res("resistance_physical") + "/" + icon_res("resistance_magic") + " + " + icon_res("resistance_missile") + " + " + icon_res("resistance_fire") + '||'
                armour_text += "max " + stat_str(kv_rules["ward_save_max_value"]) + "%" + "|| " + '||'
                armour_text += "All attacks deal an additional 1 unblockable damage"
                new_row["text"] = armour_text

            if key == "unit_stat_localisations_tooltip_text_stat_morale":
                morale_text = "Leadership mechanics: ||"
                morale_text += "total hp loss:" + '||'
                morale_text += indent_str(2) + " 10% " + smart_str(
                    kv_morale["total_casualties_penalty_10"]) + " 20% " + smart_str(
                    kv_morale["total_casualties_penalty_20"]) + " 30% " + smart_str(
                    kv_morale["total_casualties_penalty_30"]) + " 40% " + smart_str(
                    kv_morale["total_casualties_penalty_40"]) + " 50% " + smart_str(
                    kv_morale["total_casualties_penalty_50"]) + '||'
                morale_text += indent_str(2) + " 60% " + smart_str(
                    kv_morale["total_casualties_penalty_60"]) + " 70% " + smart_str(
                    kv_morale["total_casualties_penalty_70"]) + " 80% " + smart_str(
                    kv_morale["total_casualties_penalty_80"]) + " 90% " + smart_str(
                    kv_morale["total_casualties_penalty_90"]) + " 100% " + "um...?" '||'
                morale_text += "60s hp loss:" + " 10% " + smart_str(
                    kv_morale["extended_casualties_penalty_10"]) + " 15% " + smart_str(
                    kv_morale["extended_casualties_penalty_15"]) + " 33% " + smart_str(
                    kv_morale["extended_casualties_penalty_33"]) + " 50% " + smart_str(
                    kv_morale["extended_casualties_penalty_50"]) + " 80% " + smart_str(
                    kv_morale["extended_casualties_penalty_80"]) + '||'
                morale_text += "4s hp loss:" + " 6% " + smart_str(
                    kv_morale["recent_casualties_penalty_6"]) + " 10% " + smart_str(
                    kv_morale["recent_casualties_penalty_10"]) + " 15% " + smart_str(
                    kv_morale["recent_casualties_penalty_15"]) + " 33% " + smart_str(
                    kv_morale["recent_casualties_penalty_33"]) + " 50% " + smart_str(
                    kv_morale["recent_casualties_penalty_50"]) + '||'
                morale_text += "charging: " + smart_str(kv_morale["charge_bonus"]) + " timeout " + stat_str(float(kv_morale["charge_timeout"]) / 10) + "s||"
                morale_text += "attacked in" + " side " + smart_str(
                    kv_morale["was_attacked_in_flank"]) + " back " + smart_str(
                    kv_morale["was_attacked_in_rear"]) + '||'
                morale_text += "general's death: " + smart_str(
                    kv_morale["ume_concerned_general_dead"]) + " recent death or retreat " + smart_str(
                    kv_morale["ume_concerned_general_died_recently"]) + '||'
                morale_text += "army loses: " + smart_str(
                    kv_morale["ume_concerned_army_destruction"]) + " power lost: " + stat_str((1 - float(kv_morale["army_destruction_alliance_strength_ratio"])) * 100) + "% and balance is " + stat_str((1.0 / float(kv_morale["army_destruction_enemy_strength_ratio"])) * 100) + '%||'
                morale_text += "wavering:" + " " + stat_str(kv_morale["ums_wavering_threshold_lower"]) + "-" + stat_str(kv_morale["ums_wavering_threshold_upper"]) + '||'
                morale_text += indent_str(2) + "must spend at least " + stat_str(float(kv_morale["waver_base_timeout"]) / 10) + "s wavering before routing||"
                morale_text += "broken:" + " " + stat_str(kv_morale["ums_broken_threshold_lower"]) + "-" + stat_str(kv_morale["ums_broken_threshold_upper"]) + '||'
                morale_text += indent_str(2) + "max rally count before shattered " + stat_str(float(kv_morale["shatter_after_rout_count"]) - 1) + '||'
                morale_text += "shock rout if 4s hp loss is over " + stat_str(kv_morale["recent_casualties_shock_threshold"]) + "% and morale < 0"
                new_row["text"] = morale_text

            if key == "unit_stat_localisations_tooltip_text_scalar_speed":
                new_text += "|| || Fatigue effects: ||"
                for fatigue_level in fatigue_order:
                    new_text += fatigue_level + ": "
                    for stat in fatigue_effects[fatigue_level]:
                        new_text += " " + stat_icons[stat] + "" + stat_str(float(fatigue_effects[fatigue_level][stat]) * 100) + "%"
                    new_text += '||'

                new_text += " || Tiring/Resting per 1/10 second: ||"
                kv_fatigue_vals = ["idle", "ready", "walking", "walking_artillery", "running", "running_cavalry", "charging", "combat", "shooting", "climbing_ladders"]
                for fatigue_val in kv_fatigue_vals:
                    new_text += fatigue_val + " " + smart_str(kv_fatigue[fatigue_val], affinity=-1) + '||'

                kv_fatigue_vals = ["gradient_shallow_movement_multiplier", "gradient_steep_movement_multiplier", "gradient_very_steep_movement_multiplier"]
                for fatigue_val in kv_fatigue_vals:
                    new_text += fatigue_val + " " + smart_str(float(kv_fatigue[fatigue_val]) + 100, affinity=-1) + '%' + '||'

            if key == "unit_stat_localisations_tooltip_text_stat_melee_attack":
                new_text += "|| ||Melee hit chance formula: ||" + stat_str(kv_rules["melee_hit_chance_base"]) + "% + attacker " + icon("icon_stat_attack") + " - defender " + icon("icon_stat_defence") + '||'
                new_text += "(min: " + stat_str(kv_rules["melee_hit_chance_min"]) + " max: " + stat_str(kv_rules["melee_hit_chance_max"]) + ")"

            if key == "unit_stat_localisations_tooltip_text_stat_melee_defence":
                new_text += "|| ||Melee defense when attacked in" + " side " + stat_str(float(kv_rules["melee_defence_direction_penalty_coefficient_flank"]) * 100) + "% back " + stat_str(float(kv_rules["melee_defence_direction_penalty_coefficient_rear"]) * 100) + "%" + '||'
                new_text += "Melee hit chance formula: ||" + stat_str(kv_rules["melee_hit_chance_base"]) + "% + attacker " + icon("icon_stat_attack") + " - defender " + icon("icon_stat_defence") + '||'
                new_text += "(min: " + stat_str(kv_rules["melee_hit_chance_min"]) + " max: " + stat_str(kv_rules["melee_hit_chance_max"]) + ")"

            if key == "unit_stat_localisations_tooltip_text_stat_charge_bonus":
                new_text += "|| ||Charge bonus lasts for " + stat_str(kv_rules["charge_cool_down_time"] + "s") + " after first contact, linearly going down to 0. ||"
                new_text += "Charge bonus is added to melee attack and weapon damage. The additional weapon damage is split between ap and base dmg according to the unit's current ratio||"
                new_text += "All attacks on routed units are using charge bonus *" + stat_str(kv_rules["pursuit_charge_bonus_modifier"]) + '||'
                new_text += " || Bracing: ||"
                new_text += indent_str(2) + "bracing is a multiplier (clamped to " + stat_str(kv_rules["bracing_max_multiplier_clamp"]) + ") to the mass of the charged unit for comparison vs a charging one||"
                new_text += indent_str(2) + "to brace the unit must stand still in formation (exact time to get in formation varies) and not attack/fire||"
                new_text += indent_str(2) + "bracing will only apply for attacks coming from the front in a " + stat_str(float(kv_rules["bracing_attack_angle"]) * 2) + "° arc||"
                new_text += indent_str(2) + "bracing from ranks: 1: " + stat_str(1.0) + " ranks 2-" + stat_str(kv_rules["bracing_calibration_ranks"]) + " add " + stat_str((float(kv_rules["bracing_calibration_ranks_multiplier"]) - 1) / (float(kv_rules["bracing_calibration_ranks"]) - 1)) + '||'

            if key == "unit_stat_localisations_tooltip_text_stat_weapon_damage":
                new_text += "|| ||Height relative to target affects damage by up to +/-" + stat_str(float(kv_rules["melee_height_damage_modifier_max_coefficient"]) * 100) + "% at +/- " + stat_str(kv_rules["melee_height_damage_modifier_max_difference"]) + 'm'

            if key == "unit_stat_localisations_tooltip_text_scalar_missile_range":
                new_text += "|| ||Trees/scrub block " + stat_str(float(kv_rules["missile_target_in_cover_penalty"]) * 100) + "% of incoming missiles" + '||'
                new_text += "Friendly fire uses hitboxes that are " + stat_str(kv_rules["projectile_friendly_fire_man_height_coefficient"]) + " higher and " + stat_str(kv_rules["projectile_friendly_fire_man_radius_coefficient"]) + " wider " + "||  ||"
                new_text += "Accuracy is determined by a few parameters" + '||'
                new_text += "Calibration range, beyond accuracy falls greatly" + '||'
                new_text += "Calibration area, area where all shots land" + '||'
                new_text += "The longer the range and smaller the area the better" + '||'
                new_text += 'due to technical limits those are only visible in the "hover here for stats" on the unit card' + '||'
                # todo: things like missile penetration. lethality seems to contradict other stat descriptions but doesn't seem obsolete as they weren't there in shogun2  # need to do more testing before adding them in

            if key == "unit_stat_localisations_tooltip_text_stat_missile_strength":
                new_text += "|| ||Height relative to target affects damage by up to +/-" + stat_str(float(kv_rules["missile_height_damage_modifier_max_coefficient"]) * 100) + "% at +/- " + stat_str(kv_rules["missile_height_damage_modifier_max_difference"]) + 'm' + '||'

            # todo: more kv_rules values: missile, collision, etc
            new_row["text"] += new_text
        db_writer.write()


def attribute_descriptions(kv_morale):
    with TWLocDBReader("unit_attributes") as db_reader:
        db_writer = db_reader.make_writer()
        for new_row in db_reader.rows_iter:
            db_writer.new_rows.append(new_row)
            new_text = ""
            key = new_row["key"]
            stat = {}
            if key == "unit_attributes_bullet_text_causes_fear":
                new_text += "||fear aura " + smart_str(kv_morale["ume_concerned_unit_frightened"]) + " range " + stat_str(kv_morale["general_aura_radius"]) + ""
            if key == "unit_attributes_bullet_text_causes_terror":
                new_text += "||terror " + "enemy leadership <= " + stat_str(kv_morale["morale_shock_terror_morale_threshold_long"]) + " in range " + stat_str(kv_morale["terror_effect_range"]) + " instant-shock-routes enemy for " + stat_str(kv_morale["morale_shock_rout_timer_long"]) + "s||"
                new_text += "next terror immunity lasts for " + stat_str(kv_morale["morale_shock_rout_immunity_timer"]) + "s"
            if key == "unit_attributes_bullet_text_encourages":
                new_text += "||encourage aura " + " full effect range " + stat_str(kv_morale["general_aura_radius"]) + "m linear drop to 0 at " + stat_str(float(kv_morale["general_aura_radius"]) * float(kv_morale["inspiration_radius_max_effect_range_modifier"])) + "m||"
                new_text += "general's effect in full effect range " + smart_str(
                    kv_morale["general_inspire_effect_amount_min"]) + '||'
                new_text += "encourage unit's effect in full effect range " + smart_str(
                    kv_morale["unit_inspire_effect_amount"])
            if key == "unit_attributes_bullet_text_strider":
                new_text += "||this includes speed decrease on slopped terrain, melee and missile dmg reduction from being downhill, ground_stat_type, fatigue penalties from terrain, etc."
            for s in stat:
                new_text += '||' + s + ": " + stat_str(stat[s])
            new_row["text"] += new_text
        db_writer.write()


def random_localisation_strings(kv_rules, fatigue_order, fatigue_effects, stat_icons):
    with TWLocDBReader("random_localisation_strings") as db_reader:
        db_writer = db_reader.make_writer()
        for new_row in db_reader.rows_iter:
            db_writer.new_rows.append(new_row)
            new_text = ""
            key = new_row["key"]

            if key == "random_localisation_strings_string_modifier_icon_tooltip_shield":
                new_text += "|| Shields only block projectiles from the front in a " + stat_str(float(kv_rules["shield_defence_angle_missile"]) * 2) + "° arc"
            if "random_localisation_strings_string_fatigue" in key:
                for fatigue_level in fatigue_order:
                    if ("fatigue_" + fatigue_level) not in key:
                        continue
                    for stat in fatigue_effects[fatigue_level]:
                        new_text += " " + stat_icons[stat] + " " + stat_str(float(fatigue_effects[fatigue_level][stat]) * 100) + "%"
            new_row["text"] += new_text
        db_writer.write()


def rank_icon(rank):
    if int(rank) == 0:
        return "[]"
    return icon("experience_" + str(rank))


def component_texts(stat_icons):
    # getting locally required info
    xp_bonuses = {}
    with TWDBReader("unit_experience_bonuses_tables") as db_reader:
        for row in db_reader.rows_iter:
            key = row["stat"].replace("stat_", "", 1)
            xp_bonuses[key] = row

    # getting locally required info
    rank_bonuses = {}
    with TWDBReader("unit_stats_land_experience_bonuses_tables") as db_reader:
        for row in db_reader.rows_iter:
            key = row["xp_level"]
            # rank_fatigue_bonus[key] = row["fatigue"]
            result = {}
            rank = int(key)
            result["fatigue"] = stat_str(row["fatigue"])
            for bonus_stat in xp_bonuses:
                stat_row = xp_bonuses[bonus_stat]
                growth_rate = float(stat_row["growth_rate"])
                growth_scalar = float(stat_row["growth_scalar"])
                if growth_rate == 0:
                    # verified ingame that the stats are using math rounding to integer for exp bonuses
                    result[bonus_stat] = stat_str(round(growth_scalar * rank))
                else:  # "base"+"^" + stat_str(growth_rate) + "*" + stat_str(growth_scalar * rank)
                    result[bonus_stat] = stat_str(round((30.0 ** growth_rate) * growth_scalar * rank)) + " " + stat_str(round((60.0 ** growth_rate) * growth_scalar * rank))
            rank_bonuses[key] = result

    with TWLocDBReader("uied_component_texts") as db_reader:
        db_writer = db_reader.make_writer()
        for new_row in db_reader.rows_iter:
            db_writer.new_rows.append(new_row)
            new_text = ""
            key = new_row["key"]

            # todo: add unit wipe info

            if key == "uied_component_texts_localised_string_experience_tx_Tooltip_5c0016":
                new_text += "|| XP rank bonuses (melee attack and defense list values for base 30 and 60 as their bonus depends on the base value of the stat): ||"
                for rank in range(1, 10):
                    new_text += rank_icon(rank)
                    stats = rank_bonuses[str(rank)]
                    for stat in stats:
                        new_text += stat_icons[stat] + " " + stats[stat] + " "
                    new_text += '||'
            new_row["text"] += new_text
        db_writer.write()


def main():
    reload_data = True
    if reload_data:
        extract_packfiles()

    # unit_abilities localizations
    unit_ability_loc_reader = TWLocDBReader("unit_abilities")
    unit_ability_loc_writer = unit_ability_loc_reader.make_writer()

    # set parameters used in multiple functions
    ability_details = read_to_dict(TWDBReader("unit_special_abilities_tables"))
    projectile_types = read_to_dict(TWDBReader("projectiles_tables"))
    missile_weapon_junctions, missile_weapon_for_junction = get_missile_weapon_junctions()

    projectiles_explosions = read_to_dict(TWDBReader("projectiles_explosions_tables"))

    fatigue_order = ["active", "winded", "tired", "very_tired", "exhausted"]

    stat_icons = {"accuracy": "accuracy", "armour": icon("icon_stat_armour"),
                  "charge_bonus": icon("icon_stat_charge_bonus"), "charging": icon("icon_stat_charge_bonus"),
                  "fatigue": icon("fatigue"), "melee_attack": icon("icon_stat_attack"),
                  "melee_damage_ap": icon("modifier_icon_armour_piercing"), "melee_defence": icon("icon_stat_defence"),
                  "morale": icon("icon_stat_morale"), "range": icon("icon_stat_range"),
                  "reloading": icon("icon_stat_reload_time"), "speed": icon("icon_stat_speed")}

    kv_rules = read_column_to_dict(TWDBReader("_kv_rules_tables"), "key", "value")
    kv_morale = read_column_to_dict(TWDBReader("_kv_morale_tables"), "key", "value")

    unit_abilities_table(unit_ability_loc_writer, ability_details, projectile_types, missile_weapon_for_junction, projectiles_explosions)

    land_unit_to_spawn_info = main_units_tables(missile_weapon_junctions, projectile_types, projectiles_explosions)

    ability_descriptions(unit_ability_loc_reader, unit_ability_loc_writer, projectile_types, ability_details,
                         land_unit_to_spawn_info, projectiles_explosions)

    fatigue_effects = get_fatigue_effects(fatigue_order)

    component_texts(stat_icons)

    stat_descriptions(kv_rules, kv_morale, fatigue_order, fatigue_effects, stat_icons)

    attribute_descriptions(kv_morale)

    random_localisation_strings(kv_rules, fatigue_order, fatigue_effects, stat_icons)

    make_package()


if __name__ == '__main__':
    main()

# there's a dynamic accuracy stat that could be displayed on the unit panel, but it's overlapped by attributes and doesn't seem useful (doesn't include the marksmanship bonus)

# todo: unit purchasable effects
# todo: entity collision rules:
# REVAMPED ENTITY COLLISION RULES
# Previously, every collision interaction result (knockback, knockdown and so on) was checked every game tick between every entity. Following a review, we have now added a 2-second grace period between these checks between specific entities. Previously, stats such as Knock Ignore Chance were notably less effective than they were intended to be. The reason for this is that an entity pushing over another might be causing 10 checks a second against this, and the unit only has to fail one to go flying. Additionally, this caused a general overperformance of larger entities since they effectively multiplied their chance to knock things they ran into by trying-it-til-it-works. Under the new system, any collision that results in a knock reaction is first rolled against by the knock ignore chance; if the entity makes or fails this check, they are now immune to further knock reactions FROM THAT SPECIFIC OTHER ENTITY for 2 seconds. This ONLY happens if the interaction results in a knock reaction (incidental entity vs entity brushing does not consume your opportunity for a knock).

# What does this mean in practical terms?

# todo: unit brace tag
# BRACING BEHAVIOUR FOR CHARACTERS

# Characters are generally much sturdier on their feet, some notably sturdy characters (Ungrim! He can brace now too!) are almost impossible to knock down
# All units should generally be a little sturdier, though units that were always going to be knocked down due to sheer mass and speed differences will be unaffected
# It should be harder on average to pull through units attempting to pin you in place, as you no longer get 10 attempts per second to knock down entities you’re walking through.
# BRACING BEHAVIOUR FOR CHARACTERS
# Following the discussions around why bracing cannot be performed by the majority of units, we’ve moved to a system where we tag which units can brace manually. This replaces the previous system where bracing was based on a series of logical tests with the unit. We now manually tag who should be able to brace. Under the previous system only multi-entity infantry and monstrous infantry could brace, but that has now expanded to infantry and monstrous infantry single-entity characters. Additionally, any charge defense attribute now also enables bracing for the unit.

# To clarify: characters who are engaged in melee and facing their targets retain their braced status while fighting. This allows them to be far more resistant to knockdowns while actively facing off against bigger creatures or other characters. This is not a new behavior but is notably apparent for single entities compared to multi-entity units.

# And yes, Ungrim does now finally beat that arch nemesis of his. (Ungrim 1 – Feral Stegadon 57213)


# todo: unit hide in forest tag
# Who Can Hide in the Forest?

# We took a look at which units can hide in the forest recently, as there were several inconsistencies in how this attribute was being distributed. We’ve now generated some criteria that units must abide by if they should have any hope of hiding in the forests of the Warhammer World:

# Infantry and Cavalry have always been able to hide in the forest, so no changes there
# Chariots can now hide in forests, whereas they couldn’t previously. We felt that since cavalry could hide, this felt like an arbitrary inconsistency, so now all Chariots can hide
# This affects all single and multi-entity chariots, including Corpse Carts, War Wagons and Snotling Pump Wagons
# Monstrous Infantry were a web of inconsistencies. Kroxigors and Skinwolves could hide in the forest, whilst Trolls and Fimir could not. This inconsistency has been fixed, so now all ground-based multiple-entity Monstrous Infantry can hide in forests
# This change benefits the following units: All Troll Units, Dragon Ogres (not Shaggoths though, nosiree), Animated Hulks, Chaos Spawn, Crypt Horrors and Fimir Warriors
# Large monsters cannot Hide in Forest as they are absolute chonkers. However, some shorter monsters can still Hide in Forest (example: Brood Horror, Ancient Salamander)
# Additionally, units that look like trees can also Hide in Forest
# Flying Units cannot hide in the Forest, because they fly over the Forest, thus they were never in the Forest to begin with
# War Machines are generally large and loud, so they cannot hide in the forest… much to Ikit Claw’s dismay
# Artillery pieces are cumbersome, so they also cannot hide in forests
# Bolt Throwers, on the other hand, are comparatively small and light for Artillery pieces, so they can hide in forests
# The Casket of Souls can no longer hide in forests. No matter how much Nehekharan magic the Tomb Kings have, they can’t cover up the fact that this unit is a literal vortex of screaming souls, trying to burst out of a casket, that’s rumbling along on a bed of skulls. Not so sneaky.

# todo: projectile table new entry
# Projectile Vegetation Grace Periods

# Projectiles now can pass through trees for a limited time after being created. This is a global rule that applies to all non-artillery units. This behavior lasts for a limited duration after the projectile is fired, relative to the speed of the projectile. Significantly reducing instances of units firing weapons into trees that are a few feet from them.
