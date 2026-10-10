"""Extra situation rows for the class-scene builder.

Each row is (skill, prompt, acceptable answer, rubric, spoken line).
"""

from __future__ import annotations


def _rows() -> list[tuple[str, str, str, str, str]]:
    return []


def driver_scene_rows() -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []

    users = [
        ("a child chasing a ball", "Stop and wait. A ball means the child is about to follow it."),
        ("a person with a white cane", "Stop and yield. Do not honk or wave them to hurry."),
        ("a person using a wheelchair", "Stop if they are entering your path and wait until they are clear."),
        ("a cyclist taking a narrow lane", "Stay behind. Do not squeeze past in the same lane."),
        ("a cyclist in the bike lane beside your turn", "Let the cyclist pass before you turn across the bike lane."),
        ("an oncoming motorcycle", "Treat the motorcycle as a vehicle. Yield if your turn would cross its path."),
        ("a horse and rider", "Slow down and pass wide. Do not honk."),
        ("a pedestrian already in the crosswalk", "Wait until they are across. Do not roll into the crosswalk."),
        ("a jogger in dark clothes in your lane", "Slow immediately and pass only with a clear adjacent lane."),
        ("a farm tractor ahead", "Wait to pass until the centerline and the oncoming gap both allow it."),
        ("a delivery driver stepping out from a van", "Cover the brake and yield. Do not pass close to the open door."),
        ("a person pushing a stroller off the curb", "Stop. Give the stroller the crosswalk."),
        ("a skateboarder rolling off the sidewalk", "Slow and cover the brake. Do not assume they will stay on the sidewalk."),
        ("a rideshare car stopped in the lane with a door open", "Change lanes if you can, or wait. Do not squeeze past the open door."),
        ("a blind pedestrian with a guide dog", "Stop and yield. Do not honk, and do not call the dog."),
        ("a road crew member walking between cones", "Slow to the work-zone speed and give them the lane. Do not pass close."),
        ("a bicyclist signaling a left turn from the lane", "Yield. Their signal is a turn, not an invitation to pass on the left."),
        ("a motorcycle filtering slowly between stopped cars", "Hold your lane and do not open a door or drift sideways into the rider."),
        ("a school crossing guard with a stop sign", "Stop and stay stopped until the guard releases traffic."),
        ("an older adult moving slowly in the crosswalk", "Wait until they are all the way across. Do not roll forward to rush them."),
        ("a person picking up something they dropped in your lane", "Stop. They are bent over in the lane and may stand up into your path."),
        ("a dog off leash running toward the road", "Slow and cover the brake. Do not swerve into the oncoming lane."),
    ]
    places = [
        ("Marked crosswalk", "They are in a marked crosswalk, so you yield even if you also have a green light."),
        ("Mid-block", "There is no crosswalk, but they are in the road. Slow and let them clear. Do not aim past them."),
        ("School zone", "Children are nearby, so take the school speed and expect another person to follow."),
        ("Driveway exit", "You are leaving a driveway, so sidewalk users and street traffic both come before you."),
        ("Roundabout entry", "Yield before you enter. Do not stop inside the circle to sort it out."),
        ("Rain at dusk", "They are harder to see in rain and low light. Slow earlier than you would at noon."),
        ("Parked-car door", "A door is opening into the lane. Leave room so you do not hit the person or the door."),
        ("Freeway shoulder", "Do not stop in a live freeway lane. Move right only if you can do it safely, and do not drift into the shoulder where they are standing."),
        ("Unmarked rural junction", "Cross traffic may not see you. Yield if they are already in the junction, and do not pull out in front of them."),
        ("Parking-lot aisle", "People walk between cars here. Creep, and stop for anyone in the aisle."),
        ("Bike-lane merge", "You are crossing a bike lane. Yield to the rider before you move over."),
        ("Hill crest", "You cannot see over the crest. Slow until you can see the person and the opposing lane."),
        ("One-way street", "Pull toward the curb on your right to give them room. Do not use the opposing direction; there isn't one."),
        ("Construction taper", "Follow the cones, slow down, and do not use the closed lane to get around them."),
    ]
    for place, place_rule in places:
        for user, user_rule in users:
            rows.append((
                "vulnerable-users",
                f"{place}: {user} is in your path. What should you do?",
                f"{user_rule} {place_rule}",
                f"{user_rule} {place_rule}",
                user_rule,
            ))

    defects = [
        ("The left headlight is out and it is dusk.", "Do not drive until both headlights work.", "Both headlights are required. One lamp out is not a night trip.", "Fix the headlight before you go."),
        ("The brake pedal sinks slowly to the floor while the car is parked.", "Do not drive. The brakes need repair.", "A sinking pedal is a brake failure waiting on the road.", "Park it. Do not start the trip."),
        ("A tire shows cord through the tread.", "Replace the tire before you drive.", "Cord showing means the tire can blow. It is not a 'drive gently' tire.", "That tire is done. Do not drive on it."),
        ("The windshield has a crack in the driver's view.", "Do not drive until the glass is repaired. You need a clear view.", "A crack in the driver's line of sight is a no-go.", "Clear the view before you drive."),
        ("The horn does not work.", "Repair the horn before you rely on the car in traffic.", "The horn is required safety equipment, not an accessory.", "No horn: fix it before you mix with traffic."),
        ("The driver-side mirror is missing.", "Replace the mirror before you drive.", "You need the mirror to see beside and behind you.", "No mirror: do not drive."),
        ("Exhaust fumes smell inside the cabin.", "Do not drive with people in the car. Exhaust in the cabin is carbon monoxide.", "Fumes inside mean stop using the car until the leak is fixed.", "Get out. Do not drive it."),
        ("The windshield wipers smear and will not clear rain.", "Do not start a trip in rain until the wipers clear the glass.", "If you cannot see through rain, you cannot drive in it.", "Fix the wipers before a wet trip."),
        ("Ice covers the windows and you can see only a small patch.", "Scrape every window clear, including the lights, before you move.", "A peephole in the ice is not a clear view.", "Clear all the glass first."),
        ("Snow is piled on the roof and hood.", "Clear the snow off the roof, hood, lights, and windows so it does not slide onto your glass or the car behind.", "Roof snow becomes a windshield full of snow when you brake.", "Brush the snow off before you roll."),
        ("A seat belt does not latch.", "Do not carry a person in that seat, and do not drive if it is the driver's belt.", "A belt that will not latch is not a restraint.", "No latch: that seat stays empty."),
        ("A rear-facing infant seat is buckled in front of an active airbag.", "Move the seat to the back. Do not leave a rear-facing infant in front of an airbag.", "An airbag can injure a rear-facing infant.", "Back seat for the rear-facing seat."),
        ("A child under 2 is in a forward-facing seat.", "Turn the child rear-facing unless they already meet the height or weight exception your seat allows, and use the back seat.", "California keeps infants rear-facing until age 2 unless they are at least 40 pounds or 40 inches.", "Under 2: rear-facing, in the back."),
        ("A 6-year-old is using only an adult lap belt and is under 4 feet 9.", "Use a booster or car seat in the back until the child is 8 or at least 4 feet 9.", "Children under 8 need a child seat or booster unless they are 4 feet 9 or taller.", "Booster in the back for that child."),
        ("The driver's license is at home and the registration is expired.", "Do not drive. You need a valid license with you and current registration.", "Expired registration and no license is not a legal trip.", "Park the car until both are in order."),
        ("You smell gasoline near the filler neck.", "Do not drive and do not start the engine. Get the leak checked.", "A fuel leak is a fire risk.", "Engine off. Do not drive."),
        ("The defroster cannot clear fog from the inside of the glass.", "Wait until you can see, or do not go. A fogged windshield is a vision failure.", "If you cannot see the road, you are not ready to drive.", "Clear the glass before you move."),
        ("An open container of beer is in the cup holder and you have not been drinking.", "Take it out of the passenger area before you drive. An open container there is illegal.", "The open container itself is the offense, even if you are sober.", "The open beer does not ride in the cabin."),
        ("Your phone mount blocks the corner of the windshield.", "Move it so it does not sit in the driver's view.", "A mount in the line of sight hides pedestrians and signals.", "Get the mount out of your view."),
        ("The check-engine light is on and the car is shaking.", "Do not start a highway trip. Have it looked at. Shaking plus a warning light is not 'just a sensor.'", "A shake with a warning light can be a stall or a wheel. Stay off the freeway.", "Do not take it on the highway."),
    ]
    for prompt, action, rubric, spoken in defects:
        rows.append(("pre-trip", prompt + " What should you do?", action, rubric, spoken))

    nights = [
        ("high beams", "an oncoming car within 500 feet", "Switch to low beams."),
        ("high beams", "you are within 300 feet behind another car", "Switch to low beams so you do not blind the driver ahead."),
        ("no lights", "it is 40 minutes after sunset", "Turn the headlights on. They are required from 30 minutes after sunset."),
        ("no lights", "dust cuts visibility under 1,000 feet at noon", "Turn on low beams. The 1,000-foot rule applies in daylight too."),
        ("high beams", "dense fog", "Use low beams. High beams reflect back and hide the road."),
        ("parking lights only", "a dark rural highway", "Use headlights, not parking lights. Parking lights do not light the road for you."),
        ("headlights on", "a curve where you cannot see the end", "Slow so you can stop inside the distance your lights reach."),
        ("high beams", "a driver flashes you because your beams are in their eyes", "Drop to low beams. Do not flash back and hold the high beams."),
    ]
    for lights, moment, action in nights:
        rows.append((
            "night-lights",
            f"Your {lights} are in use and {moment}. What should you do?",
            action,
            action,
            action.split(".")[0] + ".",
        ))

    zones = [
        ("a flagger with a STOP paddle", "a green light farther down the zone", "Stop for the flagger. The paddle overrides the green light."),
        ("a posted work-zone speed of 25", "workers standing at the lane line", "Do not exceed 25, and slow more if the workers are close. Fines are often higher here."),
        ("orange barrels shifting your lane", "the old white lines still visible underneath", "Follow the barrels, not the old lines."),
        ("a pilot car", "a one-lane work zone", "Follow the pilot car. Do not pass it or the line of cars it leads."),
        ("a worker with their back to traffic", "you want to pass close to save time", "Slow and give the worker a full lane of space if you can. Do not squeeze by."),
        ("fresh oil and loose gravel", "a 45 mph sign just before the patch", "Slow below the number. Fresh gravel grabs the tires."),
        ("a lane closed ahead sign", "traffic still moving in your lane", "Merge early into the open lane. Do not race to the closure."),
        ("an exit ramp used as a work entrance", "trucks pulling on slowly", "Leave a gap. Do not pass a slow truck on the ramp."),
    ]
    for device, detail, action in zones:
        rows.append((
            "work-zone",
            f"You see {device}. Also, {detail}. What should you do?",
            action,
            action,
            action.split(".")[0] + ".",
        ))

    rails = [
        ("lights flashing, gate up, no train visible", "Stop and wait. Do not go around. The gate can still be coming down."),
        ("gate down, lights flashing", "Stop and stay stopped. Never drive around the gate."),
        ("a stop sign at the crossing and no train", "Stop 15 to 50 feet from the nearest rail, look both ways, then go if it is clear."),
        ("traffic stopped on the far side of the tracks", "Wait behind the line. Do not stop on the rails."),
        ("you stalled on the tracks and a train horn sounds", "Get everyone out and away from the tracks, then call for help. Do not stay in the car to restart."),
        ("a crossbuck only, no lights, and you cannot see down the curve", "Slow, look and listen, and be ready to stop. A crossbuck means yield to any train."),
        ("multiple tracks and a train just passed", "Wait. A second train can be hidden by the first. Do not go as soon as the first clears."),
        ("the pavement is marked with an X and RR", "That marking is the advance warning. Slow and be ready to stop at the crossing."),
    ]
    for scene, action in rails:
        rows.append((
            "railroad",
            f"At a railroad crossing: {scene}. What should you do?",
            action,
            action,
            action.split(".")[0] + ".",
        ))

    crashes = [
        ("You rear-end a car. Everyone says they are fine, but a passenger is dizzy.", "Call emergency help, stay at the scene, and exchange information. Do not leave because the cars can still move.", "Dizziness is an injury. Stay and report."),
        ("You scrape a parked car and the owner is gone.", "Leave your name and address in a note, and notify law enforcement as required. Do not drive off unnamed.", "A parked-car hit still requires you to identify yourself."),
        ("Your car hits a dog and the owner is not there. The dog runs off.", "Stop, try to find the owner or call local authorities, and do not leave without making a report if the rules require it.", "An animal crash is still a stop. Do not disappear."),
        ("You and the other driver disagree about the lane. There are no injuries and the cars can move.", "Move the cars out of the lane if it is safe, exchange license and insurance information, and report if the damage requires it.", "No injury does not mean you skip exchanging information."),
        ("Someone is hurt and a bystander wants to pull them out of the car.", "Do not move an injured person unless there is a fire or other immediate danger. Call emergency services.", "Moving an injured person can make the injury worse."),
        ("You caused a crash and your phone is ringing with a lawyer ad.", "Stay, help, and exchange information first. Do not leave to take the call.", "The scene comes before the phone."),
        ("The other car drives off after hitting you.", "Get a plate and a description if you can do it safely, call police, and do not chase them.", "A hit-and-run is a report, not a pursuit."),
        ("Your airbags deployed and the car is drivable.", "Do not keep driving it on the freeway. Get it off the road and have it towed or checked. Airbags deployed means the car took a real hit.", "Airbags out: get off the road and do not continue the trip."),
    ]
    for prompt, action, rubric in crashes:
        rows.append(("crashes", prompt + " What should you do?", action, rubric, action.split(".")[0] + "."))

    checks = [
        ("You want to pass on the right using the paved shoulder.", "Do not. The shoulder is not a passing lane."),
        ("You want to pass a bike and the next lane is full. The gap beside the bike is about two feet.", "Wait. California requires at least three feet, and two feet is not enough."),
        ("A car is stopped at a crosswalk and you want to pass it on the left.", "Do not pass. You cannot see who is crossing in front of that car."),
        ("You are in a shared center left-turn lane and want to drive in it for two blocks.", "Leave it. That lane is only for slowing and turning left, not for travel."),
        ("You drift onto the shoulder and want to yank the wheel back.", "Ease off the gas and steer gently back onto the pavement. A yank can flip the car."),
        ("Your GPS says to turn left and a sign says NO LEFT TURN.", "Obey the sign. Recalculate the route."),
        ("You are first in line at a green light and the far side of the intersection is full of stopped cars.", "Stay behind the line until you can clear the far side."),
        ("A funeral procession with headlights on is crossing in front of you.", "Wait until it passes. Do not cut through it."),
        ("You see a wrong-way driver on a one-way street.", "Pull to the right curb and stop. Call for help. Do not try to pass them on the left."),
        ("Your trailer starts to sway.", "Ease off the gas and hold the wheel straight. Do not brake hard."),
        ("A truck's trailer is beside your door on the freeway.", "Speed up or drop back. Do not linger in the truck's blind spot."),
        ("You need a freeway exit and a solid white line is at your wheel.", "Stay on the freeway. Take the next exit. Do not cross the solid line."),
    ]
    for prompt, action in checks:
        rows.append(("judgment", prompt + " What should you do?", action, action, action.split(".")[0] + "."))
    return rows


def food_scene_rows() -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    groups = [
        ("a pregnant guest", "Listeria and undercooked eggs are a higher risk in pregnancy."),
        ("a resident in a nursing home", "Older adults are a higher risk for Listeria and severe foodborne illness."),
        ("a child under five", "Young children are a higher risk. Do not serve them undercooked animal food."),
        ("a guest receiving chemotherapy", "A weakened immune system means no raw or undercooked animal foods and no guesswork on allergens."),
        ("a daycare lunch", "The children are a high-risk group. Cook animal foods fully and keep cold food at 41°F or below."),
    ]
    foods = [
        ("unpasteurized soft cheese", "Do not serve it. Offer a pasteurized cheese instead.", "Soft cheese made from unpasteurized milk is a Listeria risk for this guest."),
        ("a sunny-side-up egg with a runny yolk", "Cook the egg until the yolk is firm, to the temperature for the service, or offer something else.", "A runny egg is not the default for a high-risk guest."),
        ("cold deli turkey held at 41°F and date-marked on day 3", "You may serve the turkey. It is cold enough and inside the seven-day date mark.", "Deli meat is allowed when it stayed at 41°F and is inside its date."),
        ("cold deli turkey with no date and unknown age", "Do not serve it. Discard unmarked ready-to-eat meat you cannot date.", "Unknown-age deli meat is a Listeria risk. Discard it."),
        ("raw sprouts on a sandwich", "Leave the sprouts off. Raw sprouts are a high-risk garnish for this guest.", "Raw sprouts stay off the plate for high-risk guests."),
        ("a rare hamburger", "Cook the burger to 155°F for 17 seconds. Do not serve it rare.", "Ground beef for a high-risk guest is cooked to 155°F, not rare."),
        ("unpasteurized juice", "Do not pour it. Offer pasteurized juice.", "Unpasteurized juice is not for a high-risk guest."),
        ("a reheated casserole at 165°F", "You may serve it. 165°F meets reheating for hot holding and for a high-risk plate.", "165°F is the reheating temperature. This plate can go."),
        ("cut melon that has been at 50°F for an unknown time", "Discard the melon. Do not chill it and serve it.", "Cut melon is TCS food. Unknown time at 50°F means discard."),
        ("sushi made with parasite-controlled fish for a healthy adult, not this guest", "Do not send the raw fish to this guest. Offer a cooked roll.", "Raw fish is the wrong plate for this high-risk guest even if the bar serves it to others."),
    ]
    for guest, why_guest in groups:
        for food, action, why_food in foods:
            rows.append((
                "high-risk-guests",
                f"You are serving {guest}. The plate would include {food}. {why_guest} What do you do?",
                action,
                why_food,
                action.split(".")[0] + ".",
            ))

    tools = [
        ("a slicer used for roast beef", "raw chicken was just sliced on it by mistake", "Stop. Wash, rinse, and sanitize the slicer before it touches any other food. Discard ready-to-eat food it already touched."),
        ("a probe thermometer", "you just checked a raw burger", "Wash, rinse, and sanitize the probe before the next food.", "A dirty probe carries bacteria into the next item."),
        ("a cutting board", "it still has raw chicken juice", "Wash, rinse, and sanitize it before ready-to-eat food. Do not flip it over and keep going."),
        ("a can opener", "the blade has dried food on it", "Wash, rinse, and sanitize the blade before you open the next can."),
        ("tongs", "they just turned raw patties and the next ticket is a bun", "Get clean tongs or wash these. Do not touch the bun with the raw-meat tongs."),
        ("a prep sink", "it was used to thaw raw chicken", "Wash, rinse, and sanitize the sink before you wash produce in it."),
        ("a hotel pan", "it held raw shrimp and you need it for cooked rice", "Wash, rinse, and sanitize the pan. A rinse is not enough."),
        ("a food processor", "it ground almonds and the next guest has a tree-nut allergy", "Wash, rinse, and sanitize it, or do not use it for that guest. Nuts are an allergen, not just dirt."),
        ("a steam-table spoon", "the handle fell into the soup", "Replace the spoon. Do not serve from a utensil whose handle was in the food if the handle was soiled."),
        ("a sanitizer cloth", "it was used on the raw-chicken table and then on a clean plate", "Discard or rewash the plate. Keep that cloth for raw areas only, stored in sanitizer between uses."),
    ]
    for tool, event, action, rubric in (
        (t[0], t[1], t[2], t[2]) for t in tools
    ):
        rows.append((
            "tools",
            f"The station has {tool}, and {event}. What do you do?",
            action,
            rubric,
            action.split(".")[0] + ".",
        ))

    defects = [
        ("swollen ends on a can of tomatoes", "Reject the can. Swelling can mean gas-producing spoilage."),
        ("a deep dent on the side seam of a can", "Reject it. A seam dent can let bacteria in."),
        ("rust around the rim of a can", "Reject it. Do not open rusty cans for service."),
        ("a broken vacuum seal on a jar, button popped", "Reject the jar. A popped lid means it is not sealed."),
        ("frozen fish with ice crystals and soft spots", "Reject it. That pattern can mean it thawed and was refrozen."),
        ("raw chicken received at 48°F", "Reject it. Cold TCS food must arrive at 41°F or below."),
        ("hot soup received at 150°F", "Accept it if the container is sound. Hot TCS food at 135°F or above may come in."),
        ("a bag of salad with slime and an off odor", "Reject it. Odor and slime are spoilage, not a rinse-and-serve."),
        ("produce boxes with gnawed holes and droppings", "Reject the gnawed boxes and tell a manager. Do not pick through them."),
        ("milk dated yesterday and at 40°F", "You may accept it if your policy allows that date and it is 41°F or below. Check the date. Do not accept it if it is past the date."),
        ("shell eggs received at 45°F", "Reject them for a typical food-handler standard that wants cold TCS food at 41°F or below, unless your local rule for shell eggs says otherwise and you have been trained on that exception. When you have not been given an exception, reject warm eggs."),
        ("a case with a leaking chemical bottle on top of flour", "Reject or discard the flour the chemical touched, and do not stack chemicals on food again."),
    ]
    for defect, action in defects:
        rows.append((
            "receiving",
            f"At the dock you find {defect}. What do you do?",
            action,
            action,
            action.split(".")[0] + ".",
        ))

    pathogens = [
        ("norovirus", "a cook vomited in the restroom and came back to plate salads", "The cook stays off food. Throw away salads they may have touched, sanitize the restroom and any handles, and tell the manager."),
        ("Salmonella", "raw chicken juice is on a green salad", "Discard the salad. Wash hands, change gloves, and sanitize the board. Salmonella from poultry is not rinsed off lettuce."),
        ("Campylobacter", "the same cutting board moves from raw chicken to sliced tomatoes", "Stop. Wash-rinse-sanitize the board and discard the tomatoes it touched."),
        ("E. coli", "a burger for a child is still pink in the center at 140°F", "Keep cooking to 155°F for 17 seconds. Do not serve a pink burger to a child."),
        ("Listeria", "opened deli ham has no date and has been in the reach-in 'for a while'", "Discard it. Ready-to-eat meat you cannot date is not served."),
        ("Staphylococcus", "a cook with an uncovered infected cut plates sandwiches", "Stop the cook, cover the wound with a bandage and glove or send them off the line, and discard the sandwiches they just touched."),
        ("Clostridium perfringens", "a deep pot of chili was left to cool on the counter overnight", "Discard the chili. Slow cooling of a big batch is how this organism grows. Do not reheat and save it."),
        ("Clostridium botulinum", "a can is swollen and a cook wants to taste it", "Do not open or taste it. Discard the can and tell the manager."),
        ("Bacillus cereus", "cooked rice sat in the danger zone all afternoon", "Discard the rice. Reheating does not fix toxins this organism can leave behind."),
        ("Hepatitis A", "a dishwasher was diagnosed and worked yesterday", "Tell the manager immediately. The person is excluded, and the manager handles the regulatory report. Do not decide on your own that yesterday was fine."),
    ]
    for name, scene, action in pathogens:
        rows.append((
            "pathogens",
            f"The concern is {name}. {scene[0].upper() + scene[1:]}. What do you do?",
            action,
            f"{name}: {action}",
            action.split(".")[0] + ".",
        ))

    clocks = [
        ("soup", "135°F to 90°F in two hours", "It missed 70°F. Reheat to 165°F and start cooling again, or discard it."),
        ("soup", "135°F to 68°F in two hours", "On track. It must reach 41°F within four more hours."),
        ("soup", "still 48°F at six hours", "Discard it. Six hours is the end of the cooling clock."),
        ("rice", "left in a six-inch-deep pan with the lid on", "Split it into shallow pans and leave them loosely covered so it can actually cool."),
        ("chili", "cooled with an ice paddle and it hit 70°F in 90 minutes", "Keep going. You still have to reach 41°F within the remaining cooling time."),
        ("pasta", "put in the walk-in while it was still 130°F in a deep pot", "Take it out of that pot. Use shallow pans or an ice bath. A deep pot will not cool in time."),
        ("gravy", "reached 41°F in five hours total, with 70°F at hour two", "You may keep it. Both stages were met."),
        ("beans", "reached 41°F in seven hours", "Discard them. Total cooling time cannot pass six hours."),
    ]
    for food, clock, action in clocks:
        rows.append((
            "cooling",
            f"You are cooling {food}: {clock}. What do you do?",
            action,
            action,
            action.split(".")[0] + ".",
        ))

    hands = [
        ("after using the restroom", "Wash with soap for 20 seconds before you return to food. Sanitizer is not a substitute."),
        ("after handling raw sausage", "Wash, then put on new gloves before ready-to-eat food."),
        ("after taking out garbage", "Wash before you touch food or clean utensils."),
        ("after blowing your nose", "Wash, and change gloves if you were wearing them."),
        ("after eating a snack in the break area", "Wash before you go back to the line."),
        ("when the gloves have been on for four hours", "Wash and change the gloves even if they look clean."),
        ("when a glove tears", "Throw it away, wash, and glove again. Do not tape the tear."),
        ("before putting on the first pair of gloves of the shift", "Wash first. Gloves go on clean hands."),
    ]
    for moment, action in hands:
        rows.append((
            "handwashing",
            f"It is {moment}. What do you do before you handle food?",
            action,
            action,
            action.split(".")[0] + ".",
        ))

    stations = [
        ("the hospital tray line", "Tell the charge nurse or diet supervisor before any tray leaves."),
        ("the daycare kitchen", "Do not feed the children a backup from the same unsafe batch."),
        ("the food truck", "You have no walk-in on the truck. If the only fix is a long chill, discard the food."),
        ("the self-serve buffet", "Pull the pan off the line first so guests stop serving themselves."),
        ("the receiving dock", "Leave it on the dock. Reject it instead of wheeling it into the kitchen."),
        ("the sushi bar", "Stop that order. Do not serve raw fish you cannot tie to a parasite-control step."),
        ("the bakery bench", "Flour dust spreads. Do not call the next batch allergen-free until the bench is cleaned."),
        ("the off-site catering table", "You cannot run back to the commissary. If you cannot reheat to 165°F or chill to 41°F here, discard it."),
        ("the grocery deli counter", "Stop the slicer and close the case before you keep selling."),
        ("the school serving line", "Hold the line. Students are a high-risk group, so do not use the food up."),
        ("the bar well", "Ice and garnishes are food. Dump contaminated ice. Do not rinse and reuse it."),
        ("the main prep table", "Stop other prep on that table until it is washed, rinsed, and sanitized."),
    ]
    problems = [
        ("Cut melon is 50°F and the time above 41°F is unknown", "Discard the melon. Unknown time in the danger zone is not fixed by a quick chill."),
        ("A cook is vomiting and wants to finish the tickets", "Send the cook home and tell the manager. Vomiting excludes them from food."),
        ("Raw chicken is stored above ready-to-eat salad", "Move the chicken to the bottom and discard salad that may have been dripped on."),
        ("The hand sink has no soap", "Restock soap and towels before anyone handles food. That sink is not optional."),
        ("A guest has a peanut allergy and a cook wants to pick the nuts off the plated food", "Remake the plate with clean tools. Picking the nuts off leaves protein behind."),
        ("The chlorine sanitizer strip reads 0 ppm and the label range is 50 to 100", "Dump the bucket and remix it until the strip is inside 50 to 100 ppm."),
        ("The chlorine bucket reads 200 ppm and the label range is 50 to 100", "Remix it. 200 ppm is too strong for that food-contact bucket."),
        ("A can on the shelf is swollen", "Do not open or taste it. Discard it and tell a manager."),
        ("Bare hands are placing pickles on ready-to-eat burgers and there is no approved bare-hand plan", "Stop. Wash and use gloves, deli paper, or tongs."),
        ("Soup is 80°F after two hours of cooling", "It missed 70°F. Reheat it to 165°F and start cooling again, or discard it."),
        ("Opened deli turkey is on day 8 at 41°F", "Discard it. Day 7 was the last day. Prep day counts as day 1."),
        ("Mouse droppings are on an open bin of rice", "Discard the rice, tell the manager, and do not scoop around the droppings."),
        ("Frozen chicken thawed on the counter overnight", "Discard it if you cannot prove the time and temperature. Counter thawing is not an allowed method."),
        ("Sanitizer is sprayed onto a greasy table", "Wash the grease off and rinse, then sanitize. Sanitizer does not cut through soil."),
        ("Ice that cooled a pan of raw chicken is about to go into drinks", "Throw that ice away. Coolant ice is not beverage ice."),
        ("An employee is eating fries over the prep table", "Move the meal to a break area. Do not eat over exposed food."),
        ("A clean plate was dried with the raw-area sanitizer cloth", "Rewash the plate. That cloth does not finish a clean plate."),
        ("Hot chili is 120°F and nobody knows when it left 135°F", "Discard the chili. Unknown time under 135°F is not a gentle reheat."),
        ("The walk-in reads 45°F", "Stop putting TCS food in it, tell the manager, and discard food that has been above 41°F for an unknown time."),
        ("The three-compartment sink is set up as sanitize, then wash, then rinse", "Reset it to wash, rinse, sanitize, then air-dry."),
        ("The quat strip reads 150 ppm and the label says 200 to 400", "Remix the quat. 150 ppm is below that label."),
        ("A cook tastes the sauce with a finger and dips again", "Stop. Discard the spoon-or-finger contact if it went back into the sauce, and taste the next check with a clean spoon used once."),
        ("Stuffed chicken is 165°F in the meat and 150°F in the stuffing", "Keep cooking until the stuffing also reaches 165°F."),
        ("Cooked rice sat in the danger zone all afternoon", "Discard the rice. Reheating does not reliably destroy toxins some bacteria leave in rice."),
    ]
    for station, first in stations:
        for lead, fix in problems:
            rows.append((
                "stations",
                f"{lead}. You are at {station}. What do you do?",
                f"{first} {fix}",
                fix,
                fix.split(".")[0] + ".",
            ))

    extra_risk = [
        ("raw oysters", "Do not serve raw oysters to this guest. Offer a cooked seafood dish."),
        ("a medium-rare steak", "This guest should get the steak cooked to at least 145°F for 15 seconds, not medium-rare, unless a clinician has cleared a different plan. Default to fully cooked."),
        ("unrefrigerated pumpkin pie with a custard filling, time unknown", "Discard it. Custard pie is a TCS food, and an unknown time warm means it is not served."),
        ("packaged pasteurized cheddar at 40°F", "You may serve the cheddar. It is pasteurized and cold."),
        ("a smoothie with raw cookie dough", "Leave the raw dough out. Raw flour and raw egg are not for this guest."),
        ("hot soup held at 150°F", "You may serve the soup. It is above 135°F."),
        ("alfalfa sprouts on the side", "Leave the sprouts off the plate."),
        ("leftover rice reheated to 165°F just now", "You may serve it. Reheating to 165°F is the right correction when the rice was cooled and stored correctly first."),
    ]
    for guest, why_guest in groups:
        for food, action in extra_risk:
            rows.append((
                "high-risk-guests",
                f"{guest.capitalize()} is the diner, and the kitchen wants to serve {food}. {why_guest} What do you do?",
                action,
                action,
                action.split(".")[0] + ".",
            ))
    return rows
