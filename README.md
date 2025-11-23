Project Purpose


The purpose of this repository is to demonstrate the work completed during the BLAZE Hackathon, held from 15/11/2025 to 23/11/2025.

The work presented here builds upon an existing project.

The existing project, Coingraze, is a project by Compay BV.

Coingraze is a project with an up and cumming userbase from local visitors to pattingfarms and zoo's (currently one private and one public instalation). There are currenlty 8 additional machines in production, planned for public instalation in 2026.

Visitors physicly at the local zoo can use the local currency (euro for now) to activate the feeders. Part of the income goes to the farm and part of it goes to Compay BV.

These feeders have build in camaras and are made available via the internet.

The website is currenly in beta testing. Users can pay using euro or bch to directly activate the feeders (quess which is fastest). During this hackathon the static BCH qr-codes were updated to Dynamic xpub derived addresses.

The app is still in development and will be launching in 2026

The app will will be promoted at all feeder locations so visitors can download it and feed their favorite animals from anywhere.

Users of the app can use a variaty of payment options to buy grain which in turn can be donated to farms to activate the feeders.

This repository has 3 main sections for what was done during the blaze hachathon:
    


    part 1. Infrastructure
    part 2. BCH payment intagration
    part 3. Cashtoken functionality


    extra:

       CoingrazeMarketing.mp4 (not a part of BLAZE)
       AppDemo.mp4




    Part 1. Infrastructure
    Own infrastructure to monitor the BCH blockchain (plus an easy demo on how to deploy this, inspired by the blaze workshop with kalisti. this should be a lot more straighforward)
     (Not actualy done during the hackathon but somewhere in he week prior to the hachathon)

     bash commands
     docker-compose stack for easy deployment
      Bitcoincash_fulcrum.yml

    Part 2. BCH payment intagration
   
    frontend
     frontend logic to fetch and display BCH transaction information.
     frontend logic to update grain balance and create notification. (closed source)
     frontend logic to get and display bch payment details.

       grain_notification.dart
       payment_options.dart
       bch_payment_details.dart
    
    
    backend

     Mockup of the relavent tables and collumns for the postgreSQL database
       models.py

     Trigger function on the postgreSQL database
       notify_bch_changes()

     Bankend logic to monitor the relavant BCH transactions.
      cashaddresgenerator.py (not created new but updated from previous project)
      address_listener_multi.py #this file is a database listner to build a set of BCH addresses to monitor for transactions
      address_monitor_multi.py #this file will monitor for incomming transactions and update the database accordingly
      fulcrum_client.py #this file is a library to interact with the fulcrum protocol.

     
     the backend logic that creates the API endpoints to fetch or stream data to the frontend is closed source.

        
    Part 3. Cashtoken funtionality
    
    ### explanations of how the eventual functionality should work ###
###########################################################################
    Egg tokens can be earned as ingame tokens (level 2 and up) and aren't nesasaraly actual cashtokens until a user connects their wallet (requirement for level up to level 3) and converts them to cashtokens.
    At level 3 the app will allow users to start Breeding Eggs by placing them in the incubator. (locking their egg tokens in a P2SH (app is not required but makes this easy for users))
    at level 4 the app will allow users to start Hatching their eggs from the incubator. (Creating NFT's from the locked eggs and burning the eggs in the proces in a P2SH using loops (app is not required but makes it easy for users))
##########################################################################
    
    Build during BLAZE:
    
    backend logic to manage in game Egg tokens (closed source)
    frontend logic to get, process and display egg token funtionality. (closed source)
    
    
    Had created some testing cashtokens on mainnet prior to the hackaton.
       tokenID: 67b0009ac753ec4b7da6b865e6afa4cebd7a70bd5c4e904516f16250164aa58c

    
    In the current design Coingraze can activate or deactivate the onchain covenants. This enables Coingraze to update the mechanisms in the future while still being fully on-chain and indipendant of any coingraze infrastructure when deployed. When the covenants ever need an update, Coingraze can deactivate the current ones, activate new ones and direct the users to these new covanants.
    
    contracts:
       BreedingManager.cash
       HatchingManager.cash
        


    Next steps will be to use cashcript-py to do the transaction building (have currenlty only done some testing with caschript-py on other contracts, this will not be publicly ready for BLAZE since the time has run up to polish this aspect of the project.)
       


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


