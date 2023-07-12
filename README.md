# Total war: More stats mod
the goal of this version is to improve the look and structure of the stat display for warhammer ONLY
(because that's what I play)

I also got my eyes on [this mod](https://github.com/thunder-zz/warhammer2damagetooltips) for improving spell tooltips clarity

I'll update the readme with stat pages that feel complete as I go

updated tooltips

![](images/new_armor_tooltip.png)

![](images/new_morale_tooltip.png)

![](images/new_melee_def_tooltip.png)

old tooltips

![](images/old_armor_tooltip.png)

![](images/old_morale_tooltip.png)

![](images/old_melee_def_tooltip.png)

## Downloading from Steam

The mods are available on steam (and seem to be doing pretty well):
* [Warhammer 2: More unit stats](https://steamcommunity.com/sharedfiles/filedetails/?id=2986936643)
* [Warhammer 3: More unit stats](PENDING UPLOAD)

## How to build and install the mod

1. Download this repository using git clone or code -> download zip menu if you're not familiar with git
2. Download a release of [RPFM](https://github.com/Frodo45127/rpfm), release 2.4.3 is the original version but anything up to [v3.0.16](https://github.com/Frodo45127/rpfm/releases/tag/v3.0.16) will work
3. place the files into the included RPFM-companion folder
4. Install a python3 interpreter, the easiest way to do it is by using Microsoft Store, python 3.8.7 is the original, but the [recent one](https://www.python.org/downloads/) should work too
5. Update the path to the RPFM.exe in your system inside the included .bat file and run it
6. If the build was successfull the mod should be installed to your RPFM my mods directory (Documents/TWMods)
7. To install open RPFM -> My mods -> atilla -> many_more_stats.pack, then select PackFile -> Install
8. Enable the rebuilt mod:
   - run the game from the steam launcher by selecting the modded tw game (if you change the game in the totalwar launcher mod manager will not be enabled)
   - open mod manager in the total war launcher
   - mark the more_stats.pack mod as active
   - click play

## Compatibility

- due to the nature of how these mods work, they aren't compatible with mods that modify base units
- also, if a mod adds new units, the new units will not have the stat descriptions
- the mods need to be regenerated for each version of the game/base packfile

## Troubleshooting

- if you run the generate.py script and you get an error from RPFM that "there has been a problem extracting the following files", you should try to extract the file using gui (open rpfm, open the data.pack file for the game, right click on the table from the error message and click extract)
- if the gui extraction fails, it's a problem with either your rpfm install or with your copy of the game, otherwise please report the issue

### Features

- Additional information added to standard tooltips
    - bonuses from experience ranks
    - factors affecting morale
    - factors affecting movement speed and fatigue
    - some details on the formulas used for stats
    - and more
- Descriptions of spells and abilities now show more numeric details on the effects
    - damage/heal values
    - cast time
    - vortex movement path
    - explosions triggered by bombardments
    - and more
- Unit's otherwise inaccessible base stats are visible when hovering over the new "Hover for base stats" entry in the unit card bullet points
    - additional melee stats (attack interval, splash damage)
    - calculations based on db stats like dp10s are shown in blue
    - environmental effects on stats (forest, water, etc)
    - details of ranged attacks: explosions, stats, trajectory
    - support units - helper unit models, along with stats for their weapons
    - secondary range weapons, secondary ammo, etc - used by units like Doomwheel, which have an automatic range attack
    - and many more
- Units that change their base stats in the campaign (weapon techs of Skaven and Greenskins for example) add a dummy ability that you can hover over to see the base stats of the replacement weapon
    - units that have campaign replacements have a "replacement_weapon_available_in_the_campaign" entry in their base stats tooltip
    - show the same weapon info as the one shown in the base stats view but for the currently available campaign weapon
