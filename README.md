Project Purpose


	The purpose of this repository is to demonstrate the work completed during the BLAZE Hackathon, held from 15/11/2025 to 23/11/2025.
	
	The work presented here builds upon an existing project.
	
	The existing project, Coingraze, is a project by Compay BV.
	
	Coingraze is a project with an up-and-coming userbase from local visitors to petting farms and zoos (currently one private and one public installation). There are currently 8 additional machines in production, planned for public installation in 2026.
	
	Visitors physically at the local zoo can use the local currency (euro for now) to activate the feeders. Part of the income goes to the farm and part of it goes to Compay BV.
	
	These feeders have built-in cameras and are made available via the internet.
	
	The website is currently in beta testing. Users can pay using euro or BCH to directly activate the feeders (guess which is fastest). During this hackathon the static BCH QR codes were updated to Dynamic xpub derived addresses.
	
	The app is still in development and will be launching in 2026
	
	The app will be promoted at all feeder locations so visitors can download it and feed their favorite animals from anywhere.
	
	Users of the app can use a variety of payment options to buy grain which in turn can be donated to farms to activate the feeders.
	
	This repository has 3 main sections for what was done during the BLAZE Hackathon:


1. Part 1. Infrastructure

2. Part 2. BCH payment integration

3. Part 3. CashToken functionality

Extra:


- CoingrazeMarketing.mp4 (not a part of BLAZE)

- AppDemo.mp4

Part 1. Infrastructure


	Own infrastructure to monitor the BCH blockchain (plus an easy demo on how to deploy this, inspired by the BLAZE workshop with Kalisti. This should be a lot more straightforward)
	
	(Not actually done during the hackathon but somewhere in the week prior to the hackathon)
	
	
	- Bash commands
	
	- docker-compose stack for easy deployment
	
	- Bitcoincash_fulcrum.yml

Part 2. BCH payment integration
	
	
	Frontend
	
	
		- Frontend logic to fetch and display BCH transaction information.
		
		- Frontend logic to update grain balance and create notification. (closed source)
		
		- Frontend logic to get and display BCH payment details.
		
		- Files:
			- grain_notification.dart
		
			- payment_options.dart
		
			- bch_payment_details.dart
	
	
	Backend
	
	
		- Mockup of the relevant tables and columns for the PostgreSQL database
			- models.py
		
		
		- Trigger function on the PostgreSQL database
			- notify_bch_changes()
		
		
		- Backend logic to monitor the relevant BCH transactions.
			- cashaddressgenerator.py (not created new but updated from previous project)
		
			- address_listener_multi.py (this file is a database listener to build a set of BCH addresses to monitor for transactions)
		
			- address_monitor_multi.py (this file will monitor for incoming transactions and update the database accordingly)
		
			- fulcrum_client.py (this file is a library to interact with the Fulcrum protocol.)
		
		
		- The backend logic that creates the API endpoints to fetch or stream data to the frontend is closed source.

Part 3. CashToken functionality

	Explanations of how the eventual functionality should work


		Egg tokens can be earned as in-game tokens (level 2 and up) and aren't necessarily actual CashTokens until a user connects their wallet (requirement for level up to level 3) and converts them to CashTokens.
		
		At level 3 the app will allow users to start Breeding Eggs by placing them in the incubator. (locking their egg tokens in a P2SH (app is not required but makes this easy for users))
		
		At level 4 the app will allow users to start Hatching their eggs from the incubator. (Creating NFTs from the locked eggs and burning the eggs in the process in a P2SH using loops (app is not required but makes it easy for users))

	Built during BLAZE:

		
		- Backend logic to manage in-game Egg tokens (closed source)
		
		- Frontend logic to get, process and display egg token functionality. (closed source)
		
		Had created some testing CashTokens on mainnet prior to the hackathon.


		- tokenID: 67b0009ac753ec4b7da6b865e6afa4cebd7a70bd5c4e904516f16250164aa58c
		
		In the current design Coingraze can activate or deactivate the on-chain covenants. This enables Coingraze to update the mechanisms in the future while still being fully on-chain and independent of any Coingraze infrastructure when deployed. When the covenants ever need an update, Coingraze can deactivate the current ones, activate new ones and direct the users to these new covenants.
		
		Contracts:
		
		
		- BreedingManager.cash
		
		- HatchingManager.cash
		
		Next steps will be to use cashscript-py to do the transaction building (have currently only done some testing with cashscript-py on other contracts, this will not be publicly ready for BLAZE since the time has run up to polish this aspect of the project.)


---

Disclaimer


This repository is provided for demonstration and educational purposes only.

It is not an official release or representation of the Coingraze project.

Coingraze and Compay BV are not responsible for the content, code, or any outcomes resulting from the use of this repository.

Use of this material is at your own discretion and risk.


---

License


This project is licensed under the following terms:


- You are free to use, copy, modify, and distribute any part of the code in this repository.

- Any derivative or redistributed work must remain publicly available under the same terms.

- There is no warranty provided — use this code at your own risk.
