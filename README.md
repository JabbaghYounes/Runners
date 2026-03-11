[![Built with Ricky](https://img.shields.io/badge/Built%20with-Ricky-ff6b35?style=for-the-badge&logo=dependabot&logoColor=white)](https://github.com/JabbaghYounes/Ricky)

Runners

Runners is a futuristic PvPvE extraction shooter built with Python and Pygame, inspired by the classic Marathon game by Bungie. Players explore a hostile map, complete challenges, loot enemies, and extract before the round ends to upgrade their characters and home base.

Features

Competitive PvP & PvE gameplay
Futuristic retro art style
15-minute extraction rounds
Loot collection and inventory management
Skill tree progression and home base upgrades
Single playable map (expandable in future updates)
AI-controlled humanoid robot enemies
Weapon attachments, armor, and consumables

Controls

Action	Key
Move	WASD
Crouch	Ctrl
Jump	Space
Sprint	Shift
Slide	C
Pick up items/weapons	E
Open map	M
Open inventory	Tab
Aim / Shoot	Mouse

Installation

Clone the repository:

git clone https://github.com/yourusername/runners.git
cd runners

Install dependencies:

pip install -r requirements.txt

Run the game:

python main.py

Requirements: Python 3.10+, Pygame 2.x


Project Structure

runners/
├─ assets/          # Sprites, sound effects, music
├─ src/             # Game source code
│  ├─ player.py
│  ├─ enemy.py
│  ├─ map.py
│  ├─ inventory.py
│  └─ main.py
├─ README.md
└─ requirements.txt


Art & Audio

Futuristic retro pixel art

Looped background music per map zone

Sound effects for shooting, enemy attacks, loot collection


Development Roadmap

Prototype player movement & shooting

Implement AI robots and PvP interactions

Build inventory & loot system

Add skill tree & home base upgrades

Expand map & zones

Polish UI/UX, audio, and performance


Contributing

Fork the repository

Create a new branch: git checkout -b feature/my-feature

Make your changes and commit: git commit -m "Add feature"

Push to the branch: git push origin feature/my-feature

Open a pull request


License

This project is licensed under the MIT License – see the LICENSE
 file for details.

Future Plans

Multiple maps & zones

More playable characters and unique abilities

Online leaderboards and matchmaking

Advanced AI behaviors for PvE robots
