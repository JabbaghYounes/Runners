PRD: Runners
1. Game Overview

Game Title: Runners

Genre: Extraction Shooter (PvPvE)

Platform: Linux & Windows (Python + Pygame)

Target Audience: Hardcore and competitive gamers

Game Summary:
A futuristic extraction shooter inspired by Marathon, where players explore a hostile map, gather loot, complete vendor challenges, fight humanoid robots and other players, and extract successfully to build their skill trees and home base.

2. Objectives

Provide competitive PvPvE gameplay with high-stakes loot extraction

Enable exploration of a futuristic, dynamic map

Let players progress by completing challenges, gaining XP, and earning money

Support a skill tree system and home base upgrades

Metrics for success: Inventory value, player level

3. Gameplay Mechanics

Player Controls:

Movement: WASD

Crouch: Ctrl

Jump: Space

Sprint: Shift

Slide: C

Pick up items/weapons: E

Open map: M

Open inventory: Tab

Aim & shoot: Mouse

Player Character:

Different characters with unique abilities

Can equip armor and consumables (healing packs, buffs)

Has skill set and level progression

Enemies:

PvE: Humanoid robots that attack when players are in range

PvP: Other players

Game Loop:

Spawn into map

Complete challenges in different map zones

Encounter PvE robots & PvP players

Collect loot & move to inventory

Extract from the map before round ends (15 minutes)

Gain XP and money, level up, upgrade skill tree/home base

Queue for next round

Scoring / Progression:

XP awarded per enemy killed

Loot rarity correlates with monetary value

Vendor challenges grant additional rewards

Power-ups / Items:

Weapon attachments (mods, scopes, barrels, etc.)

Consumables (healing, buffs)

Armor (improves survivability)

Levels / Maps:

Single map for launch; can expand later

Dynamic zones for challenges and enemy encounters

4. Visual & Audio Design

Art Style: Futuristic retro (neon, high-tech visuals)

Sprites / Assets:

Player character sprites & animations (shoot, run, crouch, slide)

Robot enemy sprites & attack animations

Environment tiles / map assets (futuristic buildings, extraction zones)

Weapon and loot item sprites

Audio:

Futuristic background music (loops per zone)

Sound effects: shooting, weapon reload, footsteps, robot attacks, loot pick-up

5. Technical Requirements

Language & Framework: Python 3.x + Pygame

Dependencies: [pygame, numpy, any other optional libraries for assets / audio]

Resolution / Screen Size: 1280x720 (adjustable)

Performance Targets: Smooth 60 FPS gameplay

Save / Load: Save inventory, skill tree, home base upgrades

6. UI / UX

Main Menu: Start Game, Settings, Exit

HUD:

Health bar

XP bar / Level indicator

Inventory quick-access

Mini-map / extraction point

Timer for round

Pause Menu: Resume, Restart, Exit

Game Over / Extraction Screen:

Loot summary

XP earned

Money gained

Option to queue next round

7. Milestones / Development Plan
Milestone	Description	Estimated Time
Prototype	Player movement, shooting, basic enemy AI	2–3 weeks
Core Mechanics	Inventory, loot pick-up, extraction logic	2–3 weeks
Map & Level	Single playable map with challenge zones	2 weeks
PvP / PvE	Implement PvP mechanics, AI behavior for robots	2–3 weeks
Skill Tree & Home Base	Leveling system, upgrades, currency	2 weeks
UI & Audio	HUD, menus, music, sound effects	1–2 weeks
Testing & Polish	Bug fixes, balance, performance	2 weeks
8. Risks & Mitigation

Performance issues: Optimize sprites and collision detection

Scope creep: Stick to MVP: 1 map, 1 character class per type initially

Asset limitations: Use placeholder sprites until final assets are ready

9. Future Enhancements

Additional maps & zones

More playable characters with unique abilities

Online leaderboards

Advanced AI behaviors for PvE robots

Multiplayer matchmaking improvements
