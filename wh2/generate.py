import csv
import os
import shutil
import subprocess
import argparse
import math

twgame="warhammer_2"
extract_path="extract"
output_path="output"
template_path="template"
mod_name="More unit stats"
install_path=os.path.expanduser("~") + f"/Documents/TWMods/{twgame}/{mod_name}.pack"
twgame_path="E:/SteamLibrary/steamapps/common/Total War WARHAMMER II"

argparser = argparse.ArgumentParser(description='Generates the mod packfile to Documents/TWMods/')
argparser.add_argument('path_to_rpfm_cli',
                   help='path to rpfm_cli.exe used for extracting and creating mod files')
argparser.add_argument('-g', dest='path_to_game', default=twgame_path,
                   help=f'path to the main directory of {twgame}(default: {twgame_path})')
argparser.add_argument('-i', dest='install_path', default=install_path,
                   help=f'path where to install the mod file (default: {install_path})')

args = argparser.parse_args()

rpfmcli_path=args.path_to_rpfm_cli
twgame_path= args.path_to_game
install_path=args.install_path

def run_rpfm(packfile, *args):
  subprocess.run([rpfmcli_path, "-v", "-g", twgame, "-p", packfile, *args], check=True)

def extract_packfiles():
  shutil.rmtree(extract_path, ignore_errors=True)
  shutil.rmtree(output_path, ignore_errors=True)
  os.makedirs(extract_path, exist_ok=True)
  run_rpfm(f"{twgame_path}/data/data.pack", "packfile", "-E", extract_path, "dummy", "db")
  run_rpfm(f"{twgame_path}/data/local_en.pack", "packfile", "-E", extract_path, "dummy", "text")

def make_package():
  shutil.copytree(template_path, output_path, dirs_exist_ok=True)
  os.makedirs(os.path.dirname(install_path), exist_ok=True)
  try:
    os.remove(install_path)
  except:
    pass
  run_rpfm(install_path, "packfile", "-n")
  for root, dirs, files in os.walk(output_path+"/db", topdown=False):
    relroot = os.path.relpath(root, output_path+"/db")
    for name in files:
      subprocess.run([rpfmcli_path, "-v", "-g", twgame, "-p", install_path, "packfile", "-a", "db" , relroot.replace("\\", "/") + "/"+ name], cwd=output_path+"/db", check=True)
  for root, dirs, files in os.walk(output_path+"/text", topdown=False):
    relroot = os.path.relpath(root, output_path+"/text")
    for name in files:
      subprocess.run([rpfmcli_path, "-v", "-g", twgame, "-p", install_path, "packfile", "-a", "text" , relroot.replace("\\", "/") + "/"+ name], cwd=output_path+"/text", check=True)
  for root, dirs, files in os.walk(output_path+"/ui", topdown=False):
    relroot = os.path.relpath(root, output_path+"/ui")
    for name in files:
      subprocess.run([rpfmcli_path, "-v", "-g", twgame, "-p", install_path, "packfile", "-a", "ui" , relroot.replace("\\", "/") + "/"+ name], cwd=output_path+"/ui", check=True)

  run_rpfm(install_path, "packfile", "-l")
  print(f"Mod package written to: {install_path}")
  

def extract_db_to_tsv(packfile, tablefile):
  run_rpfm(f"{twgame_path}/data/{packfile}", "table", "-e", tablefile)

def pack_tsv_to_db(packfile, tablefile):
  run_rpfm(f"{twgame_path}/data/{packfile}", "table", "-i", tablefile)

class TWDBRow():
  def __init__(self, key_ids, row):
    self.key_ids = key_ids
    self.row = row

  def __getitem__(self, key):
    return self.row[self.key_ids[key]]

  def __setitem__(self, key, value):
    self.row[self.key_ids[key]] = value

  def copy(self):
    return TWDBRow(self.key_ids, self.row.copy())

class TWDBReaderImpl():
  def _read_header(self):
    try:
      self.tsv_file = open(f"{extract_path}/{self.tsvfile}", encoding="utf-8")
    except FileNotFoundError:
      extract_db_to_tsv(self.packfile, f"{extract_path}/{self.tablefile}")
      self.tsv_file = open(f"{extract_path}/{self.tsvfile}", encoding="utf-8")
      
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
    outtsvfile = self.tsvfile
    if self.outtsvfile is not None:
      outtsvfile = self.outtsvfile
    return TWDBWriter(self.tablename, self.tablefile, outtsvfile, self.packfile, self.head_rows, self.key_ids)

  def data_into_writer(self):
    result = self.make_writer()
    with self as db_reader:
      for row in db_reader.rows_iter:
        result.new_rows.append(row)
    return result

class TWDBReader(TWDBReaderImpl):
  def __init__(self, tablename):
    self.tablename = tablename
    self.tablefile = "db/" + self.tablename + "/data__"
    self.tsvfile = self.tablefile + ".tsv"
    self.outtsvfile = None
    self.head_rows = None
    self.packfile = "data.pack"

class TWLocDBReader(TWDBReaderImpl):
  def __init__(self, tablename):
    self.tablename = tablename
    self.tablefile = f"text/db/{self.tablename}__.loc"
    self.tsvfile = f"text/db/{self.tablename}__.tsv"
    self.outtsvfile = f"text/db/{self.tablename}__.loc.tsv"
    self.head_rows = None
    self.packfile = "local_en.pack"

class TWDBWriter():
  def __init__(self, tablename, tablefile, tsvfile, packfile, head_rows, key_ids):
    self.tablename = tablename
    self.tablefile = tablefile
    self.tsvfile = tsvfile
    self.head_rows = head_rows
    self.key_ids = key_ids
    self.new_rows = []
    self.packfile = packfile

  def write(self):
    os.makedirs(os.path.dirname(f"{output_path}/{self.tsvfile}"), exist_ok=True)
    self.tsv_file = open(f"{output_path}/{self.tsvfile}", 'w', newline='', encoding="utf-8")
    self.tsv_writer = csv.writer(self.tsv_file, delimiter='\t', quoting=csv.QUOTE_NONE, quotechar='')
    for row in self.head_rows:
      self.tsv_writer.writerow(row)
    for row in self.new_rows:
      self.tsv_writer.writerow(row.row)
    self.tsv_file.close()
    pack_tsv_to_db(self.packfile,f"{output_path}/{self.tsvfile}")
    os.remove(f"{output_path}/{self.tsvfile}")

  def make_row(self, kv={}):
    rowval = [""] * len(self.head_rows[1])
    row = TWDBRow(self.key_ids, rowval)
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

extract_packfiles()

# shield
shields = read_column_to_dict(TWDBReader("unit_shield_types_tables"), "key", "missile_block_chance")

# melee
melee = read_to_dict(TWDBReader("melee_weapons_tables"))

# armour
armour = read_to_dict(TWDBReader("unit_armour_types_tables"))

# projectiles
projectiles = read_to_dict(TWDBReader("projectiles_tables"))

# ability phase stats
ability_phase_stats = read_to_dict_of_lists(TWDBReader("special_ability_phase_stat_effects_tables"), "phase")

# ability phase attributes
ability_phase_attrs = read_to_dict_of_lists(TWDBReader("special_ability_phase_attribute_effects_tables"), "phase")

# ability phase details - done
# requested_stance -> special_ability_stance_enums - just an animation?
# fatigue_change_ratio: This is a scalar that changes the unit's fatigue (once off) relative to the maximum. For example, -0.25 will reduce it by 25% and 1.1 will increase it by 10%
# inspiration_aura_range_mod
# ability_recharge_change: if the unit has abilities, their recharge will be changed by that amount (negative will reduce the time, positive will increase the time)
# resurrect: If ticked, when healing excess hit points will resurrect dead soldiers
# hp_change_frequency: In seconds, how often hp (hit point) change should attempt to be applied 
# heal_amount: When HP (hit points) are healed, how much total should be changed, spread amoungst the entities
# damage_chance: Per entity, per frequency, what the chance is of applying damage; the effect is not linear, mostly effective in 0.00-0.02
# damage_amount: Per entity, per frequency, what the amount of damage to apply
# max_damaged_entities: Per damage/heal frequency, how many entities can we affect (negative is no limit)
# mana_regen_mod: How much we add to the current recharge for mana per second
# mana_max_depletion_mod: How much we add to the current value for max mana depletion
# imbue_magical: Does this phase imbue the target with magical attacks?
# imbue_ignition: Does this phase imbue the target with flaming attacks?
# imbue_contact: -> special_ability_phases Does this phase imbue the target with a contact phase when attacking?
# recharge_time
# is_hidden_in_ui
# affects_allies
# affects_enemies
# replenish_ammo: How much ammunition we want to replenish when phase starts (can be negative if we want to spend), this value is in percentage of unit max ammo
ability_phase_details = read_to_dict(TWDBReader("special_ability_phases_tables"), "id")


def ability_phase_details_stats(phaseid, indent = 0, title=""):
  result = ""
  details = ability_phase_details[phaseid]
  affects_allies = "affects_allies " if details["affects_allies"] == 'true' else ""
  affects_enemies = "affects_enemies " if details["affects_enemies"] == 'true' else ""
  unbreakable = "unbreakable " if details["unbreakable"] == 'true' else ""
  cantmove = "cant_move " if details["cant_move"] == 'true' else ""
  freeze_fatigue = "freeze_fatigue " if details["freeze_fatigue"] == 'true' else ""
  fatigue_change_ratio = "fatigue_change_ratio: " + numstr(details["fatigue_change_ratio"]) + " " if details["fatigue_change_ratio"] != '0.0' else ""
  duration = "(" + numstr(details["duration"]) +"s) " if details["duration"] != "-1.0" else ""
  col = "yellow"
  if details["effect_type"] == 'positive':
    col = "green"
  elif details["effect_type"] == 'negative':
    col = "red"
  replenish_ammo = "replenish_ammo: " + numstr(details["replenish_ammo"]) +" " if details["replenish_ammo"] != "0.0" else ""
  recharge_time = "recharge_time: " + numstr(details["recharge_time"]) +" " if details["recharge_time"] != "-1.0" else ""
  mana_regen_mod = "mana_recharge_mod: " + numstr(details["mana_regen_mod"]) +" " if details["mana_regen_mod"] != "0.0" else ""
  mana_max_depletion_mod = "mana_reserves_mod: " + numstr(details["mana_max_depletion_mod"]) +" " if details["mana_max_depletion_mod"] != "0.0" else ""
  aura_range_mod = "inspiration_range_mod: " + numstr(details["inspiration_aura_range_mod"]) +" " if details["inspiration_aura_range_mod"] != "0.0" else ""
  ability_recharge_change = "reduce_current_cooldowns: " + numstr(details["ability_recharge_change"]) +" " if details["ability_recharge_change"] != "0.0" else ""
  result += indentstr(indent) + title + "[[col:" + col + "]] " + duration +  replenish_ammo +  unbreakable + mana_regen_mod + mana_max_depletion_mod + cantmove + freeze_fatigue + fatigue_change_ratio + aura_range_mod  + ability_recharge_change + recharge_time + "[[/col]]\\\\n"
  # affects_allies + affects_enemies +
  if int(details["heal_amount"]) != 0:
    resurect = "(or resurrect if full hp) " if details["resurrect"] == "true" else ""
    result += indentstr(indent+ 2) + "heal each entity " + resurect + "by " + statstr(details["heal_amount"]) + " every " + statstr(details["hp_change_frequency"] + "s") + endl

  if int(details["damage_amount"]) != 0:
    up_to = "up to " + statstr(details["max_damaged_entities"])+ " " if int(details["max_damaged_entities"]) >= 0  else ""
    chance = "chance (" + statstr(float(details["damage_chance"]) * 100)  + "%) to " if float(details["damage_chance"]) != 1.0 else ""
    result += indentstr(indent+ 2) + chance + "damage " + up_to + "entities, each by: " + ability_damage_stat(details["damage_amount"], details["imbue_ignition"], details["imbue_magical"]) + " every " + statstr(details["hp_change_frequency"] + "s") + endl

  if phaseid in ability_phase_stats:
    result += indentstr(indent+ 2) +"stats:\\\\n"
    effects = ability_phase_stats[phaseid]
    
    for effect in effects:
      how = "*" if effect["how"] == 'mult' else '+'
      if how == '+' and float(effect["value"]) < 0:
        how = ""
      result += indentstr(indent+ 2) + effect["stat"] + " " + how + statstr(round(float(effect["value"]), 2)) + "\\\\n"
  if phaseid in ability_phase_attrs:
    attrs = ability_phase_attrs[phaseid]
    result += indentstr(indent+ 2) + "attributes: "
    for attr in attrs:
      result += statstr(attr["attribute"]) + " "
    result += "\\\\n"
  if details["imbue_contact"] != "":
    result += ability_phase_details_stats(details["imbue_contact"], indent+2, "imbue_contact")
  return result

# projectiles_explosions_tables_projectiles_explosions
projectiles_explosions = read_to_dict(TWDBReader("projectiles_explosions_tables"), "key")

# projectiles_shrapnels
shrapnels = read_to_dict(TWDBReader("projectile_shrapnels_tables"), "key")

# unit_missile_weapon_junctions
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

# effect_bonus_missile_junction
effect_bonus_missile_junctions = read_to_dict_of_lists(TWDBReader("effect_bonus_value_missile_weapon_junctions_tables"), "effect")

# ground_type_to_stat_effects_tables
ground_type_stats = read_to_dict_of_dicts_of_lists(TWDBReader("ground_type_to_stat_effects_tables"), "affected_group", "ground_type")

# weapon_to_projectile
weapon_projectile = read_column_to_dict(TWDBReader("missile_weapons_tables"), "key", "default_projectile")
weapon_secondary_ammo = read_column_to_dict(TWDBReader("missile_weapons_tables"), "key", "use_secondary_ammo_pool")

# weapon additional projectiles
weapon_alt_projectile = read_column_to_dict_of_lists(TWDBReader("missile_weapons_to_projectiles_tables"), "missile_weapon", "projectile")

# engine_to_weapon
engine_weapon = {}
engine_entity = {}
engine_mounted = {}
with TWDBReader("battlefield_engines_tables") as db_reader:
  for row in db_reader.rows_iter:
    engine_weapon[row["key"]] = row["missile_weapon"]
    engine_entity[row["key"]] = row["battle_entity"]
    engine_mounted[row["key"]] = "No_Crew" in row["engine_type"]

# articulated_entity
articulated_entity = read_column_to_dict(TWDBReader("land_unit_articulated_vehicles_tables"), "key", "articulated_entity")

# mount_to_entity
mount_entity = read_column_to_dict(TWDBReader("mounts_tables"), "key", "entity")

def posstr(stat, indent = 0):
  return indentstr(indent) + "[[col:green]]" + numstr(stat) +"[[/col]]"

def negstr(stat, indent = 0):
  return indentstr(indent) + "[[col:red]]" + numstr(stat) +"[[/col]]"

def indentstr(indent):
  return ("[[col:red]] [[/col]]" * indent)

def modstr(s):
  stat = float(s)
  if stat > 0:
    return posstr(s)
  if stat < 0:
    return negstr(s)
  return statstr(s)

def negmodstr(s):
  stat = float(s)
  if stat < 0:
    return posstr(s)
  if stat > 0:
    return negstr(s)
  return statstr(s)

def difftostr(stat):
  if stat > 0:
    return posstr(stat)
  if stat < 0:
    return negstr(stat)
  return ""

def negdifftostr(stat):
  if stat > 0:
    return negstr(stat)
  if stat < 0:
    return posstr(stat)
  return ""

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

def numstr(stat):
  fstat = try_float(stat)
  if type(fstat) != float:
    return str(stat)
  ifstat = round(fstat, 0)
  if ifstat == fstat:
    return str(int(ifstat))
  return str(round(fstat, 2))

def colstr(s, col):
  return "[[col:"+ col + "]]" + s +"[[/col]]"

def statstr(stat):
  return "[[col:yellow]]" + numstr(stat) +"[[/col]]"

def derivedstatstr(stat):
  return "[[col:cooking_ingredients_group_3]]" + numstr(stat) +"[[/col]]"

def statindent(name, value, indent):
  return indentstr(indent) + name + " " "[[col:yellow]]" + numstr(value) +"[[/col]]" + endl

# bullet point enum
bullet_point_enums_writer = TWDBReader("ui_unit_bullet_point_enums_tables").data_into_writer()

# bullet point override
bullet_point_override_writer = TWDBReader("ui_unit_bullet_point_unit_overrides_tables").data_into_writer()

# bullet point descriptions
bullet_points_loc_writer = TWLocDBReader("ui_unit_bullet_point_enums").data_into_writer()

# unit names
unit_name = {}
with TWLocDBReader("land_units") as db_reader:
  for row in db_reader.rows_iter:
    key = row["key"]
    if "land_units_onscreen_name_" in key:
      key = key.replace("land_units_onscreen_name_", "", 1)
      unit_name[key] = row["text"]

# unit table
units = read_to_dict(TWDBReader("land_units_tables"))

# battle entities
battle_entities = read_to_dict(TWDBReader("battle_entities_tables"))

# battle entity stats (only used by battle personalities and officers)
bentity_stats = read_to_dict(TWDBReader("battle_entity_stats_tables"))

# land_units_officers_tables
officers = read_to_dict(TWDBReader("land_units_officers_tables"))

# battle_personalities_tables
personalities = read_to_dict(TWDBReader("battle_personalities_tables"))

# land_units_additional_personalities_groups_junctions_tables
personality_group = read_column_to_dict_of_lists(TWDBReader("land_units_additional_personalities_groups_junctions_tables"), "group", "battle_personality")

# tags:
# [[img:path]] image
# {{tr:}} - locale? (translation)
# [[col]]
def damage_stat(base, ap, ignition, magic, title="dmg"):
  typestr = ""
  if magic == "true":
    typestr+="[[img:ui/skins/default/modifier_icon_magical.png]][[/img]]"
  if float(ignition) != 0:
    typestr+="[[img:ui/skins/default/modifier_icon_flaming.png]][[/img]]"
  apppct = ""
  if float(base) != 0:
    apppct = "("  + statstr(numstr(round(float(ap) * 100 / (float(base) + float(ap)), 2)) + "%") + ")" 
  return title + ": " + statstr(base) + "+ap:" + statstr(ap) + apppct + typestr

def ability_damage_stat(base, ignition, magic, title="dmg"):
  typestr = ""
  if magic == "true":
    typestr+="[[img:ui/skins/default/modifier_icon_magical.png]][[/img]]"
  if float(ignition) != 0:
    typestr+="[[img:ui/skins/default/modifier_icon_flaming.png]][[/img]]"
  return title + ": " + statstr(base) + typestr

def icon(name):
  return "[[img:ui/skins/default/" + name + ".png]][[/img]]"

stat_icon = {"armour": icon("icon_stat_armour"), "melee_damage_ap": "melee_ap ", "fatigue": icon("fatigue"), "accuracy": "accuracy", "morale": icon("icon_stat_morale"), "melee_attack": icon("icon_stat_morale"), "charging": icon("icon_stat_charge_bonus"), "charge_bonus": icon("icon_stat_charge_bonus"), "range": icon("icon_stat_range"), "speed": icon("icon_stat_speed"), "reloading": icon("icon_stat_reload_time"), "melee_attack": icon("icon_stat_attack"), "melee_defence": icon("icon_stat_defence")}

def rank_icon(rank):
  if int(rank) == 0:
    return "[]"
  return icon("experience_" + str(rank))

def explosion_stats(explosionrow, indent = 0): 
  projectiletext = ""
  
  # detonation_duration, detonation_speed, 
  # contact_phase_effect -> special_ability_phases
  # fuse_distance_from_target - This will activate the explosion n metres from target. If n is greater than distance to target, then the explosion will occur instantly when the projectile is activated. To get beyond this, add a min_range to the projectile.
  # damage/ap is per entity hit
  # detonation_force - This is how much force is applied to determine the result of being hit, for knockbacks etc.
  # fuse_fixed_time - Fixed fuse time in s. -1 means not fixed. Use EITHER fixed fuse time or distance from target
  # affects allies - yes/no
  # shrapnel: launches another projectile (projectile_shrapnels, amount is num of projectiles )
  projectiletext += indentstr(indent) + damage_stat(explosionrow['detonation_damage'], explosionrow['detonation_damage_ap'], explosionrow['ignition_amount'], explosionrow['is_magical'], "per_entity_dmg") + endl
  projectiletext += statindent("radius", explosionrow['detonation_radius'], indent)
  if explosionrow['affects_allies'] == "false":
    projectiletext += posstr("doesn't_affect_allies", indent) + endl
  if explosionrow['shrapnel']:
    shrapnelrow = shrapnels[explosionrow['shrapnel']]
    projectiletext += statindent("explosion_shrapnel:", "", indent)
    if shrapnelrow['launch_type'] == "sector":
      projectiletext += statindent("angle", shrapnelrow['sector_angle'], 2+ indent)
    projectiletext += statindent("amount", shrapnelrow['amount'], 2 + indent)
    projectiletext += missile_stats(projectiles[shrapnelrow['projectile']], None, "", 2 + indent, False)
  if explosionrow['contact_phase_effect']:
    projectiletext += ability_phase_details_stats(explosionrow['contact_phase_effect'],  2 + indent, "contact effect")
  return projectiletext


def missile_stats(projectilerow, unit, projectilename, indent, traj = True):
  projectiletext = ""
  #projectile:
  # fired_by_mount - If this flag is on (and the firing entity is a macro entity) the mount will fire, rather than the rider
  # prefer_central_targets - Prefer entities nearer the centre of the target (rather than closest in firing arc)
  # scaling_damage - If damage calculation has to be scaled based on different rules
  # shots_per_volley - Usually units shoot 1 shot per volley, but some animations chave multiple fire points, such as multi-shot artillery units. Most of the logic isn't aware of this, so this field is for reference for those systems
  # can_roll - Can the projectile roll on the ground
  # can_bounce - can bounce between targets?
  # expire_on_impact - If true, the projectile will expire on impact, and will not stick into, or deflect off the object it hit
  # is_beam_launch_burst - Launch beams will attempt to make the vfx match the projectiles travel, and apply a clipping plane when a projectile hits something, culling the projectiles in front
  # expiry_range - If this value is positive it dictactes the maximum distance a projectile can travel before it expires
  # projectile_penetration - what entity sizes can projectile pass through and how much can penetrate before it stops
  # can_target_airborne
  # is_magical
  # ignition_amount How much do we contribute to setting things on fire. Also, if this value is greater than 0, this is considered a flaming attack
  # gravity - Use this value to make projectiles be more / less affected by gravity. This is mainly used as a representation of wind resistance, so that projectiels can hang in the air. Negative means to use 'normal' gravity. 
  # mass - Mass of the projectile.
  # burst_size - Number of shots in a single burst (value of 1 means no burst mode)
  # burst_shot_delay - Determines the delay between each shot of the same burst
  # can_damage_buildings
  # can_damage_vehicles
  # shockwave_radius
  # muzzle_velocity - This describes the speed the projectile launches at (metres per second). If it is negative, the code will calculate this value based on firing at 45 degrees, hitting at the effective range. Not used when trajectory is fixed!
  # max_elevation - This is the maximum angle that the projectile can be fired at. Generally you want it high (max 90 degrees), and above 45. Except for special cases (e.g. cannon). Not used when trajectory is fixed!
  # fixed elevation - elevation of fixed trajectory
  # projectile_number: ? free projectiles not consuming ammo?
  # spread: ?
  # collision_radius: ?
  # homing_params: steering params for the projectile, increases chance to hit?
  # overhead_stat_effect -> special_ability_phase
  # contact_stat_effect -> special_ability_phase
  # high_air_resistance
  # minimum_range
  # trajectory_sight, max_elevation
  # category: misc ignores shields
  # calibration area, distance (the area in square meter a projectile aims, and the area guaranteed to hit at the calibration_distance range)

  building = " "
  if projectilerow['can_damage_buildings'] == "true":
    building += "@buildings "
  if projectilerow['can_damage_vehicles'] == "true":
    building += "@vehicles "
  if projectilerow['can_target_airborne'] == "true":
    building += "@airborne "
  projectiletext += indentstr(indent) + damage_stat(projectilerow['damage'], projectilerow['ap_damage'], projectilerow['ignition_amount'], projectilerow['is_magical']) + building + endl

  # calibration: distance, area, spread
  volley = ""
  if projectilerow['shots_per_volley'] != "1":
    volley += "shots_per_volley " + statstr(projectilerow['shots_per_volley'])
  if projectilerow['burst_size'] != "1":
    volley += "shots_per_volley " + statstr(projectilerow['burst_size']) + " interval " +  statstr(projectilerow['burst_shot_delay'])
  if projectilerow['projectile_number'] != "1":
    volley += "projectiles_per_shot " + statstr(projectilerow['projectile_number'])
  
  central_targets = statstr("closest_target")
  if projectilerow['prefer_central_targets'] == "false":
    central_targets = statstr("central_target")

  projectiletext += indentstr(indent) + "calibration: " + "area " + statstr(projectilerow['calibration_area']) + " distance " + statstr(projectilerow['calibration_distance']) + " prefers " + central_targets + endl

  if volley != "":
    projectiletext += indentstr(indent) + volley + endl
  if unit is not None:
    projectiletext += statindent("accuracy", float(projectilerow['marksmanship_bonus']) + float(unit['accuracy']), indent)
    reloadtime = float(projectilerow['base_reload_time']) * ((100 - float(unit['accuracy'])) * 0.01)
    projectiletext += indentstr(indent) + "reload: " + "skill " + statstr(unit['reload']) + " time " + statstr(reloadtime)+ "s (base" + statstr(projectilerow['base_reload_time']) + "s)" + endl

  category = projectilerow['category']
  if category == "misc" or category == "artillery":
    category += "(ignores shields)"
  projectiletext += indentstr(indent) + "category: "+ statstr(category) + " spin " + statstr( projectilerow['spin_type'].replace("_spin", "", 1))  + endl
  if projectilerow['minimum_range'] != "0.0":
    projectiletext += statindent("min_range", projectilerow['minimum_range'], indent)

  homing = ""
  impact = ""
  if projectilerow['can_bounce'] == "true":
    impact += "bounce "
  if projectilerow['can_roll'] == "true":
    impact += "roll "
  if projectilerow['shockwave_radius'] != "-1.0":
    impact += "shockwave_radius " + projectilerow['shockwave_radius']

  if traj == True:
    # sight - celownik
    # fixed - attached to the weapon
    # fixed trajectory != fixed sight?
    # some guide: dual_low_fixed means can use both low and fixed

    # traj examples
    # - plagueclaw sight: low max elev: 60, fixed elev 45 vel 67, grav -1, mass 50
    # - warp lightning: sight low, max elev 50, fixed elev 45 vel 110, spin: none mass: 300 grav 6
    # - poison wind mortar globe: type artillery spin axe, sight fixed, max elev 56, vel 90 grav -1, mass 25, fixed elev 50
    # - ratling gun: type musket spin none, max elev 88, vel 120, grav -1, mass 5 fix elev 45
    trajectory = "trajectory:"
    trajectory += statstr( projectilerow['trajectory_sight'])
    trajectory += " vel " + statstr( projectilerow['muzzle_velocity'])
    trajectory += " max_angle " + statstr( projectilerow['max_elevation'])
    trajectory += " fixed_angle " + statstr( projectilerow['fixed_elevation'])
    trajectory += " mass " + statstr( projectilerow['mass']) # affects air resistance and shockwave force, doesn't affect speed/acceleration
    if float(projectilerow['gravity']) != -1:
      trajectory += " g " + statstr( projectilerow['gravity']) # default is 10?, affects fall/rise rate of projectile, maybe air resistance?
    projectiletext += indentstr(indent) + trajectory + endl

  if impact != "":
    projectiletext += statindent("impact", impact, indent)
  if projectilerow['spread'] != "0.0":
    projectiletext += statindent("spread", projectilerow['spread'], indent)
  if projectilerow['homing_params'] != "":
    projectiletext += statindent("homing", "true", indent)
  if projectilerow['bonus_v_infantry'] != '0':
    projectiletext += statindent("bonus vs nonlarge" ,projectilerow['bonus_v_infantry'], indent)
  if projectilerow['bonus_v_large'] != '0':
    projectiletext += statindent("bonus_vs_large ", projectilerow['bonus_v_large'], indent)
  #todo: projectile_homing details
  # projectile_scaling_damages - scales damage with somebody's health
  if projectilerow['explosion_type'] != '':
    explosionrow = projectiles_explosions[projectilerow['explosion_type']]
    projectiletext += statindent("explosion:", "", indent)
    projectiletext += explosion_stats(explosionrow, indent+2)
  return projectiletext

def meleeweapon_stats(meleeid, indent = 0):
  unit_desc = ""
  meleerow = melee[meleeid]
  # scaling_damage If damage calculation has to be scaled based on different rules
  # col max targets: Maximum targets damaged by collision attack. This cap is refreshed by collision_attack_max_targets_cooldown.
  # col max targets cooldown: Each second, this amount of targets will be removed from the max targets list, enabling the collision attacker to deal more attacks.
  # weapon_length: Relevant for pikes, cav refusal distances and close proximity. The latter picks between this and 1m + entity radius, whatever is longer, to determine weapon "reach". Chariot riders use this to check if enemies are within reach.
  # max splash targets Maximum entities to attack per splash attack animation. Note that High Priority targets (main units table) allways get treated focussed damage.
  # splash dmg multiplier: Multiplier to knock power in splash attack metadata
  # wallbreaker attribute says if can damage walls in melee
  # todo: show dmg of a full rank of units?
  building = ""
  if int(meleerow['building_damage']) > 0:
    building = " (building: "+ statstr(meleerow['building_damage'])+ ")" # what about kv_rules["melee_weapon_building_damage_mult"]?
  unit_desc += indentstr(indent) + damage_stat(meleerow['damage'], meleerow['ap_damage'], meleerow['ignition_amount'], meleerow['is_magical'], "melee_dmg") + building + endl
  unit_desc += statindent("melee_reach", meleerow['weapon_length'], indent)
  total_dmg = int(meleerow['damage']) + int(meleerow['ap_damage'])
  dp10s = (float(total_dmg) * 10) / float(meleerow['melee_attack_interval'])
  unit_desc += indentstr(indent) + "melee_interval " + statstr(meleerow['melee_attack_interval']) + " dp10s " + derivedstatstr(round(dp10s, 0)) + endl
  if meleerow['bonus_v_infantry'] != "0":
    unit_desc += statindent("bonus_v_nonlarge", meleerow['bonus_v_infantry'], indent)
  # never set:stats["bonus_v_cav"] = meleerow['bonus_v_cavalry']
  if meleerow['bonus_v_large'] != "0":
    unit_desc += statindent("bonus_v_large", meleerow['bonus_v_large'], indent)
  if meleerow['splash_attack_target_size'] != "":
    unit_desc += statindent("splash dmg:", "", indent)
    # confirmed by ca: blank means no splash damage
    unit_desc += statindent("target_size","<=" + meleerow['splash_attack_target_size'], indent + 2)
    unit_desc += indentstr(indent + 2) + "max_targets " + statstr(meleerow['splash_attack_max_attacks']) + " dmg_each " + derivedstatstr(round(total_dmg / float(meleerow['splash_attack_max_attacks']), 0))  + endl
    if float(meleerow['splash_attack_power_multiplier']) != 1.0: 
      unit_desc += statindent("knockback mult", round(float(meleerow['splash_attack_power_multiplier']), 1), indent + 2)
  if meleerow['collision_attack_max_targets'] != "0":
    unit_desc  += indentstr(indent) + " collision: max targets " + statstr(meleerow['collision_attack_max_targets']) + " recharge_per_sec " + statstr(meleerow['collision_attack_max_targets_cooldown']) + endl
  return unit_desc


def missileweapon_stats(missileweapon, unit, indent = 0, title = "ranged"):
  projectiletext = ""
  projectileid = weapon_projectile[missileweapon]
  name = ""
  if weapon_secondary_ammo[missileweapon] == "true":
    name = "(secondary ammo)"
  projectiletext += indentstr(indent) + title + name + ":" + endl
  projectilerow = projectiles[projectileid]
  projectiletext += missile_stats(projectilerow, unit, name, indent + 2)
  if missileweapon in weapon_alt_projectile:
    for altprojectileid in weapon_alt_projectile[missileweapon]:
      altprojectilerow = projectiles[altprojectileid]
      name = altprojectilerow['shot_type'].split("_")[-1]
      if name == 'default':
        name = altprojectileid
      if weapon_secondary_ammo[missileweapon] == "true":
        name += "(secondary ammo)"
      projectiletext += indentstr(indent) + title +" (" + name + "):" + endl
      projectiletext += missile_stats(altprojectilerow, unit, name, indent + 2)
  return projectiletext

endl = "\\\\n"

# unit ability doesn't have anything intesting
# unit_special_ability uses unit_ability as key according to dave
# num_uses - charges?
# active time - If this is a projectile then set -1 for active time
# activated projectiles - projectiles table
# target_friends/enemies/ground
# assume_specific_behaviour - special_abilities_behaviour_types (cantabrian circle, etc.)
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
# num_effected_enemy_unuits
# update_targets_every_frame
# clear_current_order
# targetting_aoe -> area_of_effect_displays - This is the area of effect to display when targetting
# passive_aoe -> area_of_effect_displays - This is the area of effect to display when ability has been ordered but not yet cast (like if unit has to move their to cast)
# active_aoe -> area_of_effect_displays - This is the area of effect to display when ability is currently active (has been cast)
# miscast chance - The unary chance of a miscast occuring
# miscast_explosion -> projectiles_explosions
# target_ground_under_allies
# target_ground_under_enemies
# target_self
# target_intercept_range - ?
# only_affect_owned_units - If it's affecting friendly units, it only affect those in the same army as the owner
# spawn_is_decoy - If spawning a unit the new one will be understood as a decoy of the owner one, the UI will show data for the owning one
# spawn_is_transformation - If spawning a unit will mean the owner unit will be replaced by the spawned one
ability_details_writer = TWDBReader("unit_special_abilities_tables").data_into_writer()
ability_details = read_to_dict(TWDBReader("unit_special_abilities_tables"))
ability_details_maxid = 0
for key in ability_details:
  row = ability_details[key]
  newid = int(row["unique_id"])
  if newid > ability_details_maxid:
    ability_details_maxid = newid

# unit_abilities_tables
unit_ability_writer = TWDBReader("unit_abilities_tables").data_into_writer()

# unit_sets_tables
unit_set = read_to_dict(TWDBReader("unit_sets_tables")) # tracks sets already populated
unit_set_writer = TWDBReader("unit_sets_tables").data_into_writer()

# unit_set_to_unit_junctions_tables
unit_set_to_unit_writer = TWDBReader("unit_set_to_unit_junctions_tables").data_into_writer()

# unit_set_unit_ability_junctions_tables
unit_set_ability_writer = TWDBReader("unit_set_unit_ability_junctions_tables").data_into_writer()

# effect_bonus_value_unit_set_unit_ability_junctions_tables
effect_bonus_ability_writer = TWDBReader("effect_bonus_value_unit_set_unit_ability_junctions_tables").data_into_writer()

# unit_abilities locales
ability_loc_reader = TWLocDBReader("unit_abilities")
ability_loc_writer = ability_loc_reader.make_writer()


# missile_weapon_junctions and effect_bonus_value_missile_weapon_junctions_tables - alternative projectile weapons unlocked in campaign
#  - here we add a dummy ability which shows up when the custom weapon effect is enabled in campaign
#  - example: "the very latest thing" skill of ikit claw
#  - there's units with alternatives (or multiple) upgrades (grom's cooking gives different weapon types to goblins)
# unit_special_abilities_tables - add a dummy infinite ability with no effects, will not show up in ui without this
# unit_abilities_tables - add a passive ability for every weapon effect
# unit_abilities__.loc -  add both name and tooltip entry for every added ability
# effect_bonus_value_unit_ability_junctions_tables - copy every entry from effect_bonus_value_missile_weapon_junctions_tables, replace missile weapon id with new ability key

ability_proto_map = {"key": "ikit_claw_missile_tooltip", "requires_effect_enabling": "true", "icon_name": "ranged_weapon_stat", "type": "wh_type_augment", "uniqueness": "wh_main_anc_group_common", "is_unit_upgrade": "false", "is_hidden_in_ui": "false", "source_type": "unit", "is_hidden_in_ui_for_enemy":"false"}
ability_details_proto_map = {"key": "ikit_claw_missile_tooltip", "num_uses": "-1", "active_time": "-1", "recharge_time": "-1", "initial_recharge": "-1", "wind_up_time": "0",
 "passive": "true", "effect_range": "0", "affect_self": "false", "num_effected_friendly_units": "0", "num_effected_enemy_units": "0", "update_targets_every_frame": "0", 
 "target_friends": "false", "target_enemies": "false", "target_ground": "false", "target_intercept_range": "0", "clear_current_order": "false", "unique_id": "17224802351", "mana_cost": "0",
 "min_range": "0", "miscast_chance": "0", "voiceover_state": "vo_battle_special_ability_generic_response", "additional_melee_cp": "0", "additional_missile_cp": "0",
 "target_ground_under_allies": "false", "target_ground_under_enemies": "false", "miscast_global_bonus": "false", "target_self": "true", "spawn_is_transformation": "false", "use_loop_stance": "false",
 "spawn_is_decoy": "false", "only_affect_owned_units": "false", "shared_recharge_time": "-1" }

for effectid in effect_bonus_missile_junctions:
  effectrows = effect_bonus_missile_junctions[effectid]
  for effectrow in effectrows:
    abilityid = effectid + "_" + effectrow["missile_weapon_junction"] + "_stats"
    weaponjunction = missile_weapon_for_junction[effectrow["missile_weapon_junction"]]
    weaponid = weaponjunction["missile_weapon"]
    
    abilitynamerow = ability_loc_writer.make_row()
    abilitynamerow["key"] = "unit_abilities_onscreen_name_" + abilityid
    
    abilitynamerow["text"] = weaponid.split("_", 2)[2]
    abilitynamerow["tooltip"] = "true"
    ability_loc_writer.new_rows.append(abilitynamerow)
    abilitytextrow = ability_loc_writer.make_row()
    abilitytextrow["key"] = "unit_abilities_tooltip_text_" + abilityid
    abilitytextrow["text"] = missileweapon_stats(weaponid, None, 0)
    abilitytextrow["tooltip"] = "true"
    ability_loc_writer.new_rows.append(abilitytextrow)
    abilityrow = unit_ability_writer.make_row(ability_proto_map)
    abilityrow["key"] = abilityid
    unit_ability_writer.new_rows.append(abilityrow)

    abilitydetailsrow = ability_details_writer.make_row(ability_details_proto_map)
    abilitydetailsrow["key"] = abilityid
    ability_details_maxid = ability_details_maxid + 1
    abilitydetailsrow["unique_id"] = str(ability_details_maxid)
    ability_details_writer.new_rows.append(abilitydetailsrow)

    unitid = weaponjunction["unit"]
    unitsetid = unitid
    if unitsetid not in unit_set:
      unitsetrow = unit_set_writer.make_row()
      unitsetrow["key"] = unitsetid
      unitsetrow["use_unit_exp_level_range"] = "false"
      unitsetrow["min_unit_exp_level_inclusive"] = "-1"
      unitsetrow["max_unit_exp_level_inclusive"] = "-1"
      unitsetrow["special_category"] = ""
      unit_set[unitsetid] = unitsetrow
      unit_set_writer.new_rows.append(unitsetrow)

      unitsettounitrow = unit_set_to_unit_writer.make_row()
      unitsettounitrow["unit_set"] = unitsetid
      unitsettounitrow["unit_record"] = unitid
      unitsettounitrow["unit_caste"] = ""
      unitsettounitrow["unit_category"] = ""
      unitsettounitrow["unit_class"] = ""
      unitsettounitrow["exclude"] = "false"
      unit_set_to_unit_writer.new_rows.append(unitsettounitrow)

    unitsetabilityid = unitsetid + "_" + abilityid
    unitsetabilityrow = unit_set_ability_writer.make_row()
    unitsetabilityrow["key"] = unitsetabilityid
    unitsetabilityrow["unit_set"] = unitsetid
    unitsetabilityrow["unit_ability"] = abilityid
    unit_set_ability_writer.new_rows.append(unitsetabilityrow)

    effectbonusabilityrow = effect_bonus_ability_writer.make_row()
    effectbonusabilityrow["effect"] = effectid
    effectbonusabilityrow["bonus_value_id"] = effectrow["bonus_value_id"]
    effectbonusabilityrow["unit_set_ability"] = unitsetabilityid
    effect_bonus_ability_writer.new_rows.append(effectbonusabilityrow)

unit_ability_writer.write()
ability_details_writer.write()
unit_set_writer.write()
unit_set_to_unit_writer.write()
unit_set_ability_writer.write()
effect_bonus_ability_writer.write()

# main unit table
land_unit_to_spawn_info = {}
with TWDBReader("main_units_tables") as db_reader:
  for row in db_reader.rows_iter:
      main_unit_entry = row
      # main_unit:
      # caste: Among other usages, caste allows the overriding of UI stat bar max values
      # is_high_threat: High threat units override the entity threshold checks of melee reactions. If they run into or attack a unit, the unit will instantly react, even if less than 25% of their entities are affected.
      # unit_scaling: Determines if the number of men / artillery pieces in this unit should be scaled with the gfx unit size setting (true) or not (false)
      # mount: mount on campaign map
      # tier: unit tier
      # melee_cp: Base Melee Combat Potential of this unit. Must be >= 0.0 or the game will crash on startup. This value is modified (increased) by other factors such as Rank and equipped Abilities / Items. Reduced by 20% for missile cav.
      # can_siege - If true, can attack the turn a settlement is besieged - do not need to wait to build siege equipment on the campaign map
      # is_monstrous - For voiceover : Is this unit regarded as monstrous?
      # vo_xx - voiceover
      # multiplayer_qb_cap - Multiplayer cap for quest battles, requested by Alisdair
      unit = units[main_unit_entry["land_unit"]]

      stats = {}
      indent = 0
      unit_desc = ""
      # looks like num of non-autonomous-rider officers needs to be subtracted to have accurate numbers (based on bloodwrack_shrine in dark elf roster, ikit_claw_doomwheel, etc)
      num_men = int(main_unit_entry["num_men"])

      if unit['campaign_action_points'] != "2100":
        stats["campaign_range"] = unit['campaign_action_points']
      if unit['hiding_scalar'] != "1.0":
        stats["hiding_scalar"] = unit['hiding_scalar']
      if unit['shield'] != 'none':
        stats["missile_block"] = shields[unit['shield']] + "%"
      stats["capture_power"] = unit['capture_power'] # also apparently dead vehicles have capture power?
      # land_unit
      # todo: spot dist tree/ spot dist scrub/ 
      # hiding scalar -This affects the range that the unit can be spotted at, less than 1 makes it longer, greater than 1 shorter. So 1.5 would increase the spotters range by +50%
      # sync locomotion - undead sync anim   
      # training level: deprecated
      # visibility_spotting_range_min/max
      # attribute group - lists attributes
      if main_unit_entry["is_high_threat"] == "true":
        unit_desc  += statstr("high_threat (focuses enemy attack and splash damage)") + endl

      entity = battle_entities[unit['man_entity']]
      # entity column doc
      # todo: figure out which entity are these stats taken from? mount/engine/man?
      # combat_reaction_radius: Radius at which entity will trigger combat with nearby enemy
      # fly_speed: Speed of the entity when in the air (as opposed to moving on the ground)
      # fly_charge_speed
      # fire_arc_close? - like the angle of the fire cone aiming cone for facing the target, can be seen by simple hover, not needed in stats?
      # projectile_intersection_radius_ratio: Ratio of the radius to use for projectile intersections (usually < 1)
      # projectile_penetration_resistance: Added to the projectile penetration counter. Higher number means this entity can stop projectiles more easily.
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
      # example: ikit variant doomwheel
      # officers->land units officers tables, land_units_officers(additional_personalities) -> landland_units_additional_personalities_groups_junctions -> battle_personalities(battle_entity_stats, also battle_entity) -> battle_entity_stats
      # also land_units_officers(officers) -> battle_personalities(battle_entity_stats, also battle_entity) -> battle_entity_stats,
      if unit['officers'] != "":
        officerrow = officers[unit['officers']]
        unitpersonalities = []
        if officerrow["officer_1"] != "": # officer2 is deprecated
          unitpersonalities.append(officerrow["officer_1"])
        if officerrow["additional_personalities"] != "":
          additional = personality_group[officerrow["additional_personalities"]]
          unitpersonalities.extend(additional)
      
      support_entities = []
      supportmeleeweapons = []
      meleeweaponsset = set()
      supportrangedweapons = []
      rangedeaponsset = set()

      if unit['primary_melee_weapon'] != '':
          meleeweaponsset.add(unit['primary_melee_weapon'])

      if unit['primary_missile_weapon'] != '':
          rangedeaponsset.add(unit['primary_missile_weapon'])

      if unit['engine'] != "":
        if engine_weapon[unit['engine']] != "":
          rangedeaponsset.add(engine_weapon[unit['engine']])

      for personalityid in unitpersonalities:
        unitpersonality = personalities[personalityid]
        personalityentityid = unitpersonality["battle_entity"]
        if "autonomous_rider_hero" != "true":
          # support entities (officers) which arent the autonomous rider entity count towards mass and health
          # they don't count towards speed
          support_entities.append(personalityentityid)
          num_men -= 1
        else:
          # main entities should always be the same as main entity and don't count towards mass/health
          if personalityentityid != unit['man_entity']:
            print("main entity conflict:" + personalityentityid)
          statid = unitpersonality["battle_entity_stats"]
          if statid != "":
            stats = bentity_stats[statid]
            # autonomous rider hero personalities sometimes have a weapon even if missing in land_unit_table (example: ikit claw doomwheel)
            meleeid = stats["primary_melee_weapon"]
            if meleeid != "":
              meleeweaponsset.add(meleeid)
            missileid = stats["primary_missile_weapon"]
            if missileid != "":
              rangedeaponsset.add(missileid)

      charge_speed = float(entity["charge_speed"]) * 10
      speed = float(entity["run_speed"]) * 10
      fly_speed = float(entity["fly_speed"]) * 10
      fly_charge_speed = float(entity["flying_charge_speed"]) * 10
      accel = float(entity["acceleration"])
      size = entity["size"]
      if unit['engine'] != '':
          # speed characteristics are always overridden by engine and mount, even if engine is engine_mounted == false (example: catapult), verified by comparing stats
          engine = battle_entities[engine_entity[unit['engine']]]
          charge_speed = float(engine["charge_speed"]) * 10
          accel = float(engine["acceleration"])
          speed = float(engine["run_speed"]) * 10
          fly_speed = float(engine["fly_speed"]) * 10
          fly_charge_speed = float(engine["flying_charge_speed"]) * 10
          support_entities.append(engine_entity[unit['engine']])
          # only override size when engine is used as a mount (i.e. it's something you drive, not push), verified by comparing stats; overrides mount, verified by comparing stats
          if engine_mounted[unit['engine']]:
            size = engine["size"]
      if unit['articulated_record'] != '': # never without an engine
        support_entities.append(articulated_entity[unit['articulated_record']])
      if unit['mount'] != '':
          mount = battle_entities[mount_entity[unit['mount']]]
          # both engine and mount present - always chariots
          # verified, mount has higher priority than engine when it comes to determining speed (both increasing and decreasing), by comparing stats of units where speed of mount < or >  engine
          charge_speed = float(mount["charge_speed"]) * 10
          accel = float(mount["acceleration"])
          speed = float(mount["run_speed"]) * 10
          fly_speed = float(mount["fly_speed"]) * 10
          fly_charge_speed = float(mount["flying_charge_speed"]) * 10
          support_entities.append(mount_entity[unit['mount']])
          # verified that chariots use the size of the chariot, not the mount; skip overriding
          if not (unit['engine'] != '' and engine_mounted[unit['engine']]):
            size = engine["size"]

      health = int(entity["hit_points"]) + int(unit['bonus_hit_points'])
      mass = float(entity["mass"])

      for supportid in support_entities: 
        supportentity = battle_entities[supportid]
        mass += float(supportentity["mass"])
        health += int(supportentity["hit_points"])

      stats["health (ultra scale)"] = numstr(health)
      stats["mass"] = numstr(mass)
      targetsize = "nonlarge" if size == "small" else "large"
      stats["size"] = size + " ("+ targetsize + " target)"

      if len(meleeweaponsset) > 1:
        print("melee weapon conflict (land unit):" + unit['key'])
      for meleeid in meleeweaponsset:
        unit_desc += meleeweapon_stats(meleeid)

      unit_desc += indentstr(indent) + "run_speed " + statstr(speed) + " charge " + statstr(charge_speed) + " acceleration " + statstr(accel*10) + endl
      if fly_speed != 0:
        unit_desc += indentstr(indent) + "fly_speed " + statstr(fly_speed) + " charge " + statstr(fly_charge_speed) + endl

      # land_unit -> ground_stat_effect_group -> ground_type_stat_effects
      if unit['ground_stat_effect_group'] != "" and unit['ground_stat_effect_group'] in ground_type_stats:
        ground_types = ground_type_stats[unit['ground_stat_effect_group']]
        
        unit_desc += "ground effects (can be cancelled by strider attr): " + endl
        for gtype in  ground_types:
          statdesc = gtype + ": "
          for statrow in ground_types[gtype]:
            statdesc += statrow["affected_stat"].replace("scalar_", "", 1).replace("stat_", "", 1) + " * " + statstr(statrow["multiplier"]) + " "
          unit_desc += indentstr(indent + 2) + statdesc + endl

      if unit['armour'] != '':
          armourid = unit['armour']
          armourrow = armour[armourid]

      # ammo is number of full volleys (real ammo is num volleys * num people)
      if int(unit['secondary_ammo']) != 0:
        stats["secondary_ammo"] = unit['secondary_ammo']
      
      for stat in stats:
          unit_desc += statindent(stat, stats[stat], indent)

      if main_unit_entry["unit"] in missile_weapon_junctions:
        unit_desc += statstr("ranged_weapon_replacement_available_in_campaign [[img:ui/battle ui/ability_icons/ranged_weapon_stat.png]][[/img]]") + endl

      if len(rangedeaponsset) > 1:
        print("missile weapon conflict (land unit):" + unit['key'])
      for missileweapon in rangedeaponsset:
        unit_desc += missileweapon_stats(missileweapon, unit, indent)

      for personalityid in unitpersonalities:
        unitpersonality = personalities[personalityid]
        statid = unitpersonality["battle_entity_stats"]
        if statid != "":
          stats = bentity_stats[statid]
          meleeid = stats["primary_melee_weapon"]
          if meleeid != "" and meleeid not in meleeweaponsset:
            meleeweaponsset.add(meleeid)
            supportmeleeweapons.append(meleeid)

          missileid = stats["primary_missile_weapon"]
          if missileid != "" and missileid not in rangedeaponsset:
            rangedeaponsset.add(missileid)
            supportrangedweapons.append(missileid)

      for meleeid in supportmeleeweapons:
        unit_desc += "melee_support:" + endl
        unit_desc += meleeweapon_stats(meleeid, 2)

      for missileid in supportrangedweapons:
        unit_desc += missileweapon_stats(missileid, None, 0, "ranged_support")

      spawn_info = unit_name[main_unit_entry["land_unit"]] + " (" + main_unit_entry["caste"] + ", tier " + main_unit_entry["tier"] + " men " + numstr(num_men) + ")"
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
      bullet_point_override_writer.new_rows  .append(new_override)

      bullet_name_id  =  "ui_unit_bullet_point_enums_onscreen_name_" + new_bullet_id
      bullet_tooltip_id  =  "ui_unit_bullet_point_enums_tooltip_" + new_bullet_id

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

# ability phases
ability_phases = read_column_to_dict_of_lists(TWDBReader("special_ability_to_special_ability_phase_junctions_tables"), "special_ability", "phase")

# battle vortexs - done
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
# delay: We do spawn this at the same time as usual, but we wait this time to cause damage / move / collide etc.
# num_vortexes - num of vortexes spawned
# affects_allies
# launch_source_offset- distance from launch_source
# delay_between_vortexes
vortexs = read_to_dict(TWDBReader("battle_vortexs_tables"), "vortex_key")

# projectile bombardment - done
# num_projectiles The total number of projectiles that will spawn. Their arrival times are random, within the times specified
# start_time the minimum time (seconds) that must pass before a projectile can appear
# arrival_window The time (seconds) duration that any of the projectiles can appear
# radius_spread How far away from the target this can theoretically land
# launch_source The suggested starting location of the bombardment
# launch_height_(underground)
bombardments = read_to_dict(TWDBReader("projectile_bombardments_tables"), "bombardment_key")

# ability descriptions
with ability_loc_reader as db_reader:
  for newrow in db_reader.rows_iter:
    ability_loc_writer.new_rows.append(newrow)
    if "unit_abilities_tooltip_text_" in newrow["key"]:
        descid =  newrow["key"].replace("unit_abilities_tooltip_text_", "", 1)
        result = "\\\\n\\\\n"

        if descid in ability_details:
          ability = ability_details[descid]

          if ability["passive"] == "false":
            result += statindent("cast_time", ability["wind_up_time"], 0)
            result += statindent("active_time", ability["active_time"], 0)
            initial_recharge = ""
            if (float(ability["initial_recharge"]) > 0): 
              initial_recharge = ", initial " + ability["initial_recharge"]
            result += statindent("recharge_time", ability["recharge_time"] + initial_recharge, 0)
            if float(ability["min_range"]) > 0:
              result += statindent("min_range", ability["min_range"] + initial_recharge, 0)

          if int(ability["num_effected_friendly_units"]) > 0:
            result += statindent("affected_friendly_units", ability["num_effected_friendly_units"], 0)
          if int(ability["num_effected_enemy_units"]) > 0:
            result += statindent("affected_enemy_units", ability["num_effected_enemy_units"], 0)
          if ability["only_affect_owned_units"] == "true":
            result += statindent("only_affect_owned_units", ability["only_affect_owned_units"], 0)
          if ability["update_targets_every_frame"] == "true":
            result += statindent("update_targets_every_frame", ability["update_targets_every_frame"], 0)

          if ability["assume_specific_behaviour"]:
            result += statindent("behaviour", ability["assume_specific_behaviour"], 0)
          
          if ability["bombardment"] != "":
            bombardment = bombardments[ability["bombardment"]]
            result += "Bombardment:\\\\n"
            result += statindent("num_bombs", bombardment["num_projectiles"],2)
            result += statindent("radius_spread", bombardment["radius_spread"],2)
            result += statindent("launch_source", bombardment["launch_source"],2)
            result += statindent("launch_height", bombardment["launch_height"],2)
            result += statindent("start_time", bombardment["start_time"],2)
            result += statindent("arrival_window", bombardment["arrival_window"],2)
            bomb_projectile = projectiles[bombardment["projectile_type"]]
            result += missile_stats(bomb_projectile, None, "", 2)
            result += "\\\\n"
          if ability["activated_projectile"] != "":
            result += "Projectile:"
            projectile = projectiles[ability["activated_projectile"]]
            result += missile_stats(projectile, None, "", 2)
            result += "\\\\n"
          if ability["vortex"] != "":
            result += "Vortex: \\\\n"
            indent = 2
            vortex = vortexs[ability['vortex']]
            if vortex['num_vortexes'] != "1":
              result += indentstr(indent) + " vortex count: " + statstr(vortex['num_vortexes']) + " vortexes " + statstr(vortex['delay_between_vortexes']) + "s delay inbetween" + endl
            radius = ""
            if vortex['start_radius'] == vortex['goal_radius']:
              radius = statstr(vortex['start_radius'])
            else:
              radius = "start " + statstr(vortex['start_radius']) + " goal " +  statstr(vortex['goal_radius']) + " expansion speed " +  statstr(vortex['expansion_speed'])
            result += indentstr(indent) + "radius: " + radius + endl
            result += indentstr(indent) + damage_stat(vortex['damage'], vortex['damage_ap'], vortex['ignition_amount'], vortex['is_magical']) + endl
            result += statindent("detonation_force", vortex['detonation_force'], indent)
            result += statindent("initial_delay", vortex['delay'], indent)
            result += statindent("duration", vortex['duration'], indent)
            if vortex['building_collision'] == "2.expire":
              result += indentstr(indent) + statstr("building colision expires vortex") + endl
            result += statindent("launch_source", vortex['launch_source'], indent)
            if vortex['launch_source_offset'] != "0.0":
              result += statindent("launch_source_offset", vortex['launch_source_offset'], indent)
            if float(vortex['movement_speed']) == 0:
              path = "stationary"
            elif vortex['change_max_angle'] == "0":
              path = "straight line, speed " + statstr(vortex['movement_speed'])
            else:
              path = "angle changes by " + statstr("0-"+numstr(vortex['change_max_angle'])) + " every " + statstr(vortex['move_change_freq']) + ", speed " + statstr(vortex['movement_speed'])
            result += indentstr(indent) +  "path: " + path + endl
            if vortex['affects_allies'] == "false":
              result += posstr("doesn't_affect_allies", indent) + endl
            if vortex["contact_effect"] != "":
              result += ability_phase_details_stats(phaseid, indent, "contact effect")
          if ability["spawned_unit"] != "":
            result += "Spawn: "
            if ability["spawn_is_decoy"] == "true":
              result += "(decoy) "
            if ability["spawn_is_transformation"] == "true":
              result += "(transform) "
            result += land_unit_to_spawn_info[ability['spawned_unit']]
            result += endl
          if ability["miscast_explosion"] != "":
            result += "Miscast explosion (chance:" + statstr(float(ability["miscast_chance"]) * 100) + "%):"
            explosionrow = projectiles_explosions[ability['miscast_explosion']]
            result += explosion_stats(explosionrow, 2)
            result += endl
        if descid in ability_phases:
            result += "Phases:\\\\n"
            phases = ability_phases[descid]
            i = 0
            for phaseid in phases:
              i = i + 1
              result += ability_phase_details_stats(phaseid, 2, numstr(i) + ".")
        newrow["text"] = newrow["text"] + result 

# new unit_abilities loc entries
ability_loc_writer.write()

kv_rules = read_column_to_dict(TWDBReader("_kv_rules_tables"), "key", "value")

kv_fatigue = read_column_to_dict(TWDBReader("_kv_fatigue_tables"), "key", "value")

kv_morale = read_column_to_dict(TWDBReader("_kv_morale_tables"), "key", "value")

fatigue_order = ["active", "winded", "tired", "very_tired", "exhausted"]


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

xp_bonuses = {}
with TWDBReader("unit_experience_bonuses_tables") as db_reader:
  for row in db_reader.rows_iter:
    key = row["stat"].replace("stat_", "", 1)
    xp_bonuses[key] = row

rank_bonuses = {}
with TWDBReader("unit_stats_land_experience_bonuses_tables") as db_reader:
  for row in db_reader.rows_iter:
    key = row["xp_level"]
    #rank_fatigue_bonus[key] = row["fatigue"]
    result = {}
    rank = int(key)
    result["fatigue"] = statstr(row["fatigue"])
    for bonus_stat in xp_bonuses:
      stat_row = xp_bonuses[bonus_stat]
      growth_rate = float(stat_row["growth_rate"])
      growth_scalar = float(stat_row["growth_scalar"])
      if growth_rate == 0:
        # verified in game that the stats are using math rounding to integer for exp bonuses
        result[bonus_stat] = statstr(round(growth_scalar * rank))
      else: #"base"+"^" + statstr(growth_rate) + "*" + statstr(growth_scalar * rank)
        result[bonus_stat] = statstr(round((30.0 ** growth_rate) * growth_scalar * rank)) + " " + statstr(round((60.0 ** growth_rate) * growth_scalar * rank))
    rank_bonuses[key] = result


# stat descriptions
with TWLocDBReader("unit_stat_localisations") as db_reader:
  db_writer = db_reader.make_writer()
  for newrow in db_reader.rows_iter:
    db_writer.new_rows.append(newrow)
    newtext = ""
    key = newrow["key"]
    if key == "unit_stat_localisations_tooltip_text_stat_armour":
      newtext += "|| ||Armour non-ap-dmg-reduction formula: rand(" + statstr(kv_rules["armour_roll_lower_cap"]) + ",1) * armour"
    if key == "unit_stat_localisations_tooltip_text_stat_morale":
      moraletext = "Leadership mechanics: ||"
      moraletext += "total hp loss:" + "||"
      moraletext += indentstr(2) + " 10% " + modstr(kv_morale["total_casualties_penalty_10"]) + " 20% " + modstr(kv_morale["total_casualties_penalty_20"]) + " 30% " + modstr(kv_morale["total_casualties_penalty_30"]) + " 40% " + modstr(kv_morale["total_casualties_penalty_40"]) + " 50% " + modstr(kv_morale["total_casualties_penalty_50"]) + "||"
      moraletext += indentstr(2) + " 60% " + modstr(kv_morale["total_casualties_penalty_60"]) + " 70% " + modstr(kv_morale["total_casualties_penalty_70"]) + " 80% " + modstr(kv_morale["total_casualties_penalty_80"]) + " 90% " + modstr(kv_morale["total_casualties_penalty_90"]) + " 100% " + "um...?" "||"
      moraletext += "60s hp loss:" + " 10% " + modstr(kv_morale["extended_casualties_penalty_10"]) + " 15% " + modstr(kv_morale["extended_casualties_penalty_15"]) + " 33% " + modstr(kv_morale["extended_casualties_penalty_33"])  + " 50% " + modstr(kv_morale["extended_casualties_penalty_50"])  + " 80% " + modstr(kv_morale["extended_casualties_penalty_80"]) + "||"
      moraletext += "4s hp loss:" + " 6% " + modstr(kv_morale["recent_casualties_penalty_6"]) + " 10% " + modstr(kv_morale["recent_casualties_penalty_10"]) + " 15% " + modstr(kv_morale["recent_casualties_penalty_15"]) + " 33% " + modstr(kv_morale["recent_casualties_penalty_33"]) + " 50% " + modstr(kv_morale["recent_casualties_penalty_50"]) + "||"
      moraletext += "charging: " + modstr(kv_morale["charge_bonus"]) + " timeout " + statstr(float(kv_morale["charge_timeout"]) / 10) +"s||"
      moraletext += "attacked in" + " side " + modstr(kv_morale["was_attacked_in_flank"]) + " back " + modstr(kv_morale["was_attacked_in_rear"]) + "||"
      moraletext += "army loses: " + modstr(kv_morale["ume_concerned_army_destruction"]) + " power lost: " + statstr((1 - float(kv_morale["army_destruction_alliance_strength_ratio"])) * 100) + "% and balance is " + statstr((1.0 / float(kv_morale["army_destruction_enemy_strength_ratio"])) * 100) + '%||'
      moraletext += "general's death: " +  modstr(kv_morale["ume_concerned_general_dead"]) + " recent death or retreat " + modstr(kv_morale["ume_concerned_general_died_recently"]) + "||"
      moraletext += "wavering:" + " " + statstr(kv_morale["ums_wavering_threshold_lower"])  + "-" + statstr(kv_morale["ums_wavering_threshold_upper"]) + "||"
      moraletext += indentstr(2) + "must spend at least" + statstr(float(kv_morale["waver_base_timeout"]) / 10)  + "s wavering before routing||"
      moraletext += "broken:" + " " + statstr(kv_morale["ums_broken_threshold_lower"]) + "-" + statstr(kv_morale["ums_broken_threshold_upper"]) + "||"
      moraletext += indentstr(2) + "max rally count before shattered "  + statstr(float(kv_morale["shatter_after_rout_count"]) - 1) + "||"
      moraletext += "shock rout if 4s hp loss is over " + statstr(kv_morale["recent_casualties_shock_threshold"]) + "% and morale < 0"
      newrow["text"] = moraletext
    if key == "unit_stat_localisations_tooltip_text_scalar_speed":
      newtext += "|| || Fatigue effects: ||"
      for fatigue_level in fatigue_order:
        newtext += fatigue_level + ": "
        for stat in fatigue_effects[fatigue_level]:
          newtext += " " + stat_icon[stat] + "" + statstr(float(fatigue_effects[fatigue_level][stat]) * 100) + "%"
        newtext += "||"
      newtext += " || Tiring/Resting per 1/10 second: ||"
      kvfatiguevals = ["charging", "climbing_ladders", "combat", "gradient_shallow_movement_multiplier", "gradient_steep_movement_multiplier", "gradient_very_steep_movement_multiplier",
      "idle", "limbering", "ready", "running", "running_cavalry", "running_artillery_horse", "shooting", "walking", "walking_artillery", "walking_horse_artillery"]
      for kvfatval in kvfatiguevals:
        newtext += kvfatval + " " + negmodstr(kv_fatigue[kvfatval]) + "||"
    if key == "unit_stat_localisations_tooltip_text_stat_melee_attack":
      newtext += "|| ||Melee hit chance formula: ||" + statstr(kv_rules["melee_hit_chance_base"]) + "% + attacker melee attack - defender melee defence" + "||"
      newtext += "(min: " + statstr(kv_rules["melee_hit_chance_min"]) + " max: " + statstr(kv_rules["melee_hit_chance_max"]) + ")"
    if key == "unit_stat_localisations_tooltip_text_stat_melee_defence":
      newtext += "|| ||Melee defense when attacked in" + " side " + statstr(float(kv_rules["melee_defence_direction_penalty_coefficient_flank"]) * 100) + "% back " + statstr(float(kv_rules["melee_defence_direction_penalty_coefficient_rear"]) * 100) + "%" + "||"
      newtext += "Melee hit chance formula: ||" + statstr(kv_rules["melee_hit_chance_base"]) + "% + attacker melee attack - defender melee defence" + "||"
      newtext += "(min: " + statstr(kv_rules["melee_hit_chance_min"]) + " max: " + statstr(kv_rules["melee_hit_chance_max"]) + ")"
    if key == "unit_stat_localisations_tooltip_text_stat_charge_bonus":
      newtext += "|| ||Charge bonus lasts for " + statstr(kv_rules["charge_cool_down_time"] + "s") + " after first contact, linearly going down to 0. ||"
      newtext += "Charge bonus is added to melee_attack and weapon_damage. Weapon_damage increase is split between ap and base dmg using the ap/base dmg ratio before the bonus.||"
      newtext += "All attacks on routed units are using charge bonus *" + statstr(kv_rules["pursuit_charge_bonus_modifier"]) + "||"
      newtext += " || Bracing: ||"
      newtext += indentstr(2) + "bracing is a multiplier (clamped to " +statstr(kv_rules["bracing_max_multiplier_clamp"]) + ") to the mass of the charged unit for comparison vs a charging one||"
      newtext += indentstr(2) + "to brace the unit must stand still in formation (exact time to get in formation varies) and not attack/fire||" 
      newtext += indentstr(2) + "bracing will only apply for attacks coming from the front at max " + statstr(kv_rules["bracing_attack_angle"]) + "* half-angle||"              
      newtext += indentstr(2) + "bracing from ranks: 1: " + statstr(1.0) + " ranks 2-" + statstr(kv_rules["bracing_calibration_ranks"]) + " add " + statstr((float(kv_rules["bracing_calibration_ranks_multiplier"]) - 1) / (float(kv_rules["bracing_calibration_ranks"])  - 1)) + "||"
    if key == "unit_stat_localisations_tooltip_text_stat_weapon_damage":
      newtext += "|| Terrain height difference dmg mod max: +/-" + statstr(float(kv_rules["melee_height_damage_modifier_max_coefficient"]) * 100) + "% at diff of +/- " + statstr(kv_rules["melee_height_damage_modifier_max_difference"]) + "m, linearly decreasing to 0"
    if key == "unit_stat_localisations_tooltip_text_scalar_missile_range":
      newtext += "|| ||Hit chance when shooting targets hiding in forests/scrub:" + statstr((1 - float(kv_rules["missile_target_in_cover_penalty"]))  * 100) + '||'
      newtext += "Friendly fire uses bigger hitboxes than enemy fire: height *= " + statstr(kv_rules["projectile_friendly_fire_man_height_coefficient"]) + " radius *= " + statstr(kv_rules["projectile_friendly_fire_man_radius_coefficient"]) + "||" 
      newtext += "Units with " + statstr("dual") + " trajectory will switch their aim to high if "+ statstr(float(kv_rules["unit_firing_line_of_sight_considered_obstructed_ratio"]) * 100) + "% of LOS is obstructed ||"
      newtext += "Projectiles with high velocity and low aim are much better at hitting moving enemies."
      # todo: things like missile penetration, lethality seem to contradict other stat descriptions but don't seem obsolete as they weren't there in shogun2
      # need to do more testing before adding them in
    if key == "unit_stat_localisations_tooltip_text_stat_missile_strength":
      newtext += "|| Terrain height difference dmg mod max: +/-" + statstr(float(kv_rules["missile_height_damage_modifier_max_coefficient"]) * 100) + "% at diff of +/- " + kv_rules["missile_height_damage_modifier_max_difference"] + "m, linearly decreasing to 0||"
    
    # todo: more kv_rules values: missile, collision, etc
    newrow["text"] += newtext
  db_writer.write()



# attr descriptions
with TWLocDBReader("unit_attributes") as db_reader:
  db_writer = db_reader.make_writer()
  for newrow in db_reader.rows_iter:
    db_writer.new_rows.append(newrow)
    newtext = ""
    key = newrow["key"]
    stat = {}
    if key == "unit_attributes_bullet_text_causes_fear":
      newtext += "||fear aura " + modstr(kv_morale["ume_concerned_unit_frightened"]) + " range " + statstr(kv_morale["general_aura_radius"]) +""
    if key == "unit_attributes_bullet_text_causes_terror":
      newtext += "||terror " + "enemy leadership <= " + statstr(kv_morale["morale_shock_terror_morale_threshold_long"]) + " in range " + statstr(kv_morale["terror_effect_range"]) + " instant-shock-routes enemy for " + statstr(kv_morale["morale_shock_rout_timer_long"]) + "s||"
      newtext += "next terror immunity lasts for " + statstr(kv_morale["morale_shock_rout_immunity_timer"]) + "s"
    if key == "unit_attributes_bullet_text_encourages":
      newtext += "||encourage aura " + " full effect range " + statstr(kv_morale["general_aura_radius"]) + "m linear drop to 0 at " + statstr(float(kv_morale["general_aura_radius"]) * float(kv_morale["inspiration_radius_max_effect_range_modifier"])) +  "m||"
      newtext += "general's effect in full effect range " + modstr(kv_morale["general_inspire_effect_amount_min"]) + "||"
      newtext += "encourage unit's effect in full effect range " + modstr(kv_morale["unit_inspire_effect_amount"]) 
    if key == "unit_attributes_bullet_text_strider":
      newtext += "||this includes speed decrease from uphill slope, melee and missile dmg reduction from being downhill, ground_stat_type, fatigue penalties from terrain, etc."
    for s in stat:
      newtext += "||" + s + ": " + statstr(stat[s])
    newrow["text"] += newtext
  db_writer.write()

# misc strings
with TWLocDBReader("random_localisation_strings") as db_reader:
  db_writer = db_reader.make_writer()
  for newrow in db_reader.rows_iter:
    db_writer.new_rows.append(newrow)
    newtext = ""
    key = newrow["key"]
    stat = {}

    if key == "random_localisation_strings_string_modifier_icon_tooltip_shield":
      newtext += "|| Shields only block projectiles from the front at max "+ statstr(kv_rules["shield_defence_angle_missile"]) + "* half-angle"
    if "random_localisation_strings_string_fatigue" in key:
      for fatigue_level in fatigue_order:
        if ("fatigue_" + fatigue_level) not in key:
          continue
        for stat in fatigue_effects[fatigue_level]:
          newtext += " " + stat_icon[stat] + " " + statstr(float(fatigue_effects[fatigue_level][stat]) * 100) + "%"
    newrow["text"] += newtext
  db_writer.write()

# misc strings
with TWLocDBReader("uied_component_texts") as db_reader:
  db_writer = db_reader.make_writer()
  for newrow in db_reader.rows_iter:
    db_writer.new_rows.append(newrow)
    newtext = ""
    key = newrow["key"]
    stat = {}

    if key == "uied_component_texts_localised_string_experience_tx_Tooltip_5c0016":
      newtext += "|| XP rank bonuses (melee attack and defence list values for base 30 and 60 as their bonus depends on the base value of the stat): ||"
      for rank in range(1, 10):
        newtext += rank_icon(rank)
        stats = rank_bonuses[str(rank)]
        for stat in stats:
          newtext += stat_icon[stat] + " " + stats[stat] + " "
        newtext += "||"
    newrow["text"] += newtext
  db_writer.write()

make_package()

#there's a dynamic accuracy stat that could be displayed on the unit panel, but it's overlapped by attributes and doesn't seem useful (doesn't include marksmanship bonus)

## todo: unit purchaseable effects
## todo: entity collision rules:
# REVAMPED ENTITY COLLISION RULES
# Previously, every collision interaction result (knockback, knockdown and so on) was checked every game tick between every entity. Following a review, we have now added a 2 second grace period between these checks between specific entities. Previously, stats such as Knock Ignore Chance were notably less effective than they were intended to be. The reason for this is that an entity pushing over another might actually be causing 10 checks a second against this, and the unit only has to fail one to go flying. Additionally, this caused a general overperformance of larger entities since they effectively multiplied their chance to knock things they ran into by trying-it-til-it-works. Under the new system, any collision that results in a knock reaction is first rolled against by the knock ignore chance; if the entity makes or fails this check, they are now immune to further knock reactions FROM THAT SPECIFIC OTHER ENTITY for 2 seconds. This ONLY happens if the interaction results in a knock reaction (incidental entity vs entity brushing does not consume your opportunity for a knock).

# What does this mean in practical terms?

# Characters are generally much sturdier on their feet, some notably sturdy characters (Ungrim! He can brace now too!) are almost impossible to knock down
# All units should generally be a little bit sturdier, though units that were always going to be knocked down due to sheer mass and speed differences will be unaffected
# It should be harder on average to pull through units attempting to pin you in place, as you no longer get 10 attempts per second to knock down entities you’re walking through.
# BRACING BEHAVIOUR FOR CHARACTERS
# Following the discussions around why bracing cannot be performed by the majority of units, we’ve moved to a system where we tag which units can brace manually. This replaces the previous system where bracing was based on a series of logical tests with the unit. We now manually tag who should be able to brace. Under the previous system only multi-entity infantry and monstrous infantry could brace, but that has now expanded to infantry and monstrous infantry single-entity characters. Additionally, any charge defence attribute now also enables bracing for the unit.

# To clarify: characters which are engaged in melee and facing their targets retain their braced status while fighting. This allows them to be far more resistant to knockdowns while actively facing off against bigger creatures or other characters. This is not a new behaviour, but is notably apparent for single entities compared to multi entity units.

# And yes, Ungrim does now finally beat that arch nemesis of his. (Ungrim 1 – Feral Stegadon 57213)

# todo: unit brace tag
# BRACING BEHAVIOUR FOR CHARACTERS
# Following the discussions around why bracing cannot be performed by the majority of units, we’ve moved to a system where we tag which units can brace manually. This replaces the previous system where bracing was based on a series of logical tests with the unit. We now manually tag who should be able to brace. Under the previous system only multi-entity infantry and monstrous infantry could brace, but that has now expanded to infantry and monstrous infantry single-entity characters. Additionally, any charge defence attribute now also enables bracing for the unit.

# To clarify: characters which are engaged in melee and facing their targets retain their braced status while fighting. This allows them to be far more resistant to knockdowns while actively facing off against bigger creatures or other characters. This is not a new behaviour, but is notably apparent for single entities compared to multi entity units.

## todo: unit hide in forest tag
# Who Can Hide in the Forest?

# We took a look at which units can hide in the forest recently, as there were several inconsistencies to how this attribute was being distributed. We’ve now generated some criteria that units must abide by if they should have any hope of hiding in the forests of the Warhammer World:

# Infantry and Cavalry have always been able to hide in the forest, so no changes there
# Chariots can now hide in forests, whereas they couldn’t previously. We felt that since cavalry could hide, this felt like an arbitrary inconsistency, so now all Chariots can hide
# This affects all single and multi-entity chariots, including Corpse Carts, War Wagons and Snotling Pump Wagons
# Monstrous Infantry were a web of inconsistencies. Kroxigors and Skinwolves could hide in the forest, whilst Trolls and Fimir could not. This inconsistency has been fixed, so now all ground-based multiple-entity Monstrous Infantry can hide in forests
# This change benefits the following units: All Troll Units, Dragon Ogres (not Shaggoths though, nosiree), Animated Hulks, Chaos Spawn, Crypt Horrors and Fimir Warriors
# Large monsters cannot Hide in Forest as they are absolute chonkers. However some of the shorter monsters can still Hide in Forest (example: Brood Horror, Ancient Salamander)
# Additionally, units that look like trees can also Hide in Forest
# Flying Units cannot hide in the Forest, because they fly over the Forest, thus they were never in the Forest to begin with
# War Machines are generally large and loud, so they cannot hide in the forest… much to Ikit Claw’s dismay
# Artillery pieces are cumbersome, so they also cannot hide in forests
# Bolt Throwers on the other hand, are comparatively small and light for Artillery pieces, so they can hide in forests
# The Casket of Souls can no longer hide in forests. No matter how much Nehekharan magic the Tomb Kings have, they can’t cover up the fact that this unit is a literal vortex of screaming souls, trying to burst out of a casket, that’s rumbling along on a bed of skulls. Not so sneaky.

# todo: projectile table new entry
  # Projectile Vegetation Grace Periods

  # Projectiles now have the ability to pass through trees for a limited time after being created. This is a global rule that applies to all non-artillery units. This behaviour lasts for a limited duration after the projectile is fired, relative to the speed of the projectile. Significantly reducing instances of units firing weapons into trees that are a few feet from them.
