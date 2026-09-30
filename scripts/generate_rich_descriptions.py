"""
Generate Rich Custom Descriptions & Daily Schedules for All 65 Shorts
======================================================================
Builds unique, high-CTR, scene-specific descriptions with interactive hooks,
curated comedy hashtags, and daily scheduled timestamps (1 Reel per day).
Updates instagram_queue.json and meta_business_suite_schedule.csv.
"""

import json
import csv
import sys
import io
from pathlib import Path
from datetime import datetime, timedelta

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

MEDIA_BASE = Path(r"D:\Media\shorts")
TBBT_MANIFEST = MEDIA_BASE / "diepvo8265" / "manifest.json"
QUEUE_FILE = MEDIA_BASE / "instagram_queue.json"
CSV_FILE = MEDIA_BASE / "meta_business_suite_schedule.csv"

# Custom scene hooks tailored specifically for each Big Bang Theory moment
SCENE_DETAILS = {
    1: {
        "hook": "Sheldon gives Amy the one gift nobody on Earth ever expected him to part with! 😂🎁",
        "question": "Was this Sheldon's most selfless moment in the whole series? Drop a ❤️ if you agree!",
        "tags": "#shamy #sheldonandamy #relationshipgoals #sitcomlove"
    },
    2: {
        "hook": "Nobody messes with Amy when Sheldon is around! He stands up for her in classic Sheldon fashion. 🛡️🤣",
        "question": "Would you want Sheldon defending you in an argument? Let us know below! 👇",
        "tags": "#sheldoncooper #defendingamy #sitcomclash #bazinga"
    },
    3: {
        "hook": "Sheldon goes out of his way to convince Penny not to break up with Leonard. Who knew he was such a wingman? 🤝😂",
        "question": "Did Leonard really deserve Penny or was Sheldon right all along? 🍿",
        "tags": "#pennyandleonard #sheldonwingman #tbbtrelationships #sitcomcouple"
    },
    4: {
        "hook": "Sheldon plays Scrabble with the legendary Stephen Hawking... and things get wildly competitive! ♟️🤣",
        "question": "What's the best Stephen Hawking cameo on the show? Comment below! ⬇️",
        "tags": "#stephenhawking #scrabble #physicsjokes #geniuscomedy"
    },
    5: {
        "hook": "Sheldon attempts the impossible: letting go of his cherished childhood past. It doesn't go smoothly! 📦😂",
        "question": "Can you relate to Sheldon's extreme hoarding habits? Yes or No? 😅",
        "tags": "#sheldonspast #nostalgia #collectorlife #sitcommoments"
    },
    6: {
        "hook": "Sheldon walks in on the shock of a lifetime: Mary Cooper has a new boyfriend! His face says everything. 😱🤣",
        "question": "Sheldon's reaction is pure comedy gold! Rate it from 1 to 10 below! 🔥",
        "tags": "#marycooper #sheldonsmom #familydrama #hilariousreactions"
    },
    7: {
        "hook": "Sheldon spends an unforgettable evening hanging out with James Earl Jones (Darth Vader himself)! 🎙️😂",
        "question": "Is this the greatest guest appearance in Big Bang Theory history? 🌟",
        "tags": "#jamesearljones #starwars #darthvader #legendarycameo"
    },
    8: {
        "hook": "Penny recruits Beverly Hofstadter as her secret weapon against Leonard! Talk about bringing in the heavy artillery. 🧠🤣",
        "question": "Beverly is brutal! Was Leonard right to be terrified? 😂",
        "tags": "#beverlyhofstadter #leonardsmom #psychologyjokes #coldmother"
    },
    9: {
        "hook": "Bernadette secretly forms an exclusive girls' club, and the guys are completely in the dark! 🤫😂",
        "question": "Never underestimate Bernadette! Who is your favorite female character on TBBT? 👑",
        "tags": "#bernadetterostenkowski #girlsclub #sitcomfriendships #girlpower"
    },
    10: {
        "hook": "Leonard leaves for a business trip, and Sheldon immediately starts spilling all the confidential tea to Penny! ✈️🤣",
        "question": "Can Sheldon keep a secret for more than 5 seconds? Drop your vote! 🙊",
        "tags": "#roommatesecrets #pennysheldon #whispers #classiccomedy"
    },
    11: {
        "hook": "The moment fans waited seasons for: Sheldon and Amy's official first romantic kiss! 💋😍",
        "question": "Where were you when Shamy finally kissed on the train? Absolute iconic TV moment! ❤️",
        "tags": "#shamykiss #firstkiss #trainkiss #iconictv"
    },
    12: {
        "hook": "Sheldon forces Leonard to wear an agonizingly itchy sweater to prove a point about unreturned library books! 🧶🤣",
        "question": "Was Sheldon's sweater punishment genius or pure torture? Let us know below! 💀",
        "tags": "#itchysweater #sheldonpunishment #pettyreasons #classicprank"
    },
    13: {
        "hook": "Stuart being Stuart: completely clueless and unintentionally stealing the spotlight! 🤦‍♂️😂",
        "question": "Who is the most underrated character on the entire show? Stuart fans speak up! 🙋‍♂️",
        "tags": "#stuartbloom #comicbookstore #awkwardmoments #underrated"
    },
    14: {
        "hook": "Sheldon and Amy's carefully calculated birthday plans get hit with the most unexpected interruption! 🎂🤣",
        "question": "If your birthday schedule was ruined like this, how would you react? 😂",
        "tags": "#shamybirthday #birthdayplans #sitcomchaos #bdayvibes"
    },
    15: {
        "hook": "Sheldon Cooper actually says 'I love you' to Amy Farrah Fowler for the very first time! 🥹❤️",
        "question": "Did this scene make you cry or cheer? Shamy fans unite! 😭🙌",
        "tags": "#iloveyou #shamylove #sheldongrowth #heartwarming"
    },
    16: {
        "hook": "Leonard takes Sheldon to meet their childhood science hero, but things take an unbelievable turn! 🧪😲",
        "question": "Never meet your heroes! What would you say if you met Sheldon Cooper in real life? 😆",
        "tags": "#scienceidol #childhoodhero #awkwardmeeting #sitcomgold"
    },
    17: {
        "hook": "Sheldon famously refuses to celebrate any holidays, until Amy touches his heart in a way no one else could! 🎄🥰",
        "question": "Amy really is the only person who can reach Sheldon's soul. Agree or disagree? ❤️",
        "tags": "#holidaymagic #sheldonandamy #christmasspecial #touchingmoments"
    },
    18: {
        "hook": "Leonard finally puts his foot down and demands what he wants... with mixed results! 😤🤣",
        "question": "Does Leonard stand up for himself enough against Sheldon? Tell us below! 💬",
        "tags": "#leonardhofstadter #standingup #roommatebattle #assertive"
    },
    19: {
        "hook": "Barry Kripke tries making a move on Amy, and Sheldon's sudden jealousy is pure comedy! 🥊😂",
        "question": "Kripke vs. Sheldon: Who would win in an intellectual duel? 🤺",
        "tags": "#barrykripke #jealoussheldon #rivalry #comedyduel"
    },
    20: {
        "hook": "Amy writes a steamy romance novel, and the lead character sounds suspiciously like Sheldon! 📖🔥🤣",
        "question": "Would you buy Amy Farrah Fowler's romance novel? Be honest! 😂📚",
        "tags": "#amysnovel #romancenovels #fictionwriting #hilariousbooks"
    },
    21: {
        "hook": "Sheldon realizes he wronged his friends and embarks on an official, heavily-scripted 'Apology Tour'! 📜😂",
        "question": "Has someone ever given you an apology as formal as Sheldon's? Tag them! 🏷️",
        "tags": "#apologytour #formalapology #sheldonsincerity #peaceoffering"
    },
    22: {
        "hook": "Leonard finds himself in a public moment of maximum embarrassment that he'll never live down! 🙈🤣",
        "question": "What's the most second-hand embarrassment Leonard has ever given you? 🍿",
        "tags": "#cringemoments #embarrassing #poorleonard #sitcomfails"
    },
    23: {
        "hook": "Beverly diagnoses Leonard and Penny's marriage with surgical, ruthless psychological precision! 📋🤣",
        "question": "Is Beverly the harshest mother in sitcom history? Who's worse? 😳",
        "tags": "#marriagetherapy #ruthlessmom #psychiatry #motherinlaw"
    },
    24: {
        "hook": "Sheldon loses out on the chance to become the new Professor Proton, and the meltdown is spectacular! 📺🤯",
        "question": "Did Sheldon deserve to be Professor Proton or would he have scared the kids? 😂",
        "tags": "#professorproton #sciencedrama #tvhostaudition #bazinga"
    },
    25: {
        "hook": "Sheldon tries his best to conceal his burning jealousy, but his facial expressions give him away immediately! 👀😂",
        "question": "Can you spot when someone is pretending not to be jealous? Describe the face! 😆",
        "tags": "#greenwithenvy #jealousreactions #pokerfacefail #sheldonstyle"
    },
    26: {
        "hook": "Sheldon insists he doesn't need an 'emotion machine' to understand human feelings... then proves he definitely does! 🤖🤣",
        "question": "Which of Sheldon's robot-like traits is your absolute favorite? ⚙️",
        "tags": "#emotiondetector #robotmode #vulcanlife #humanemotions"
    },
    27: {
        "hook": "Sheldon worries he's losing his childlike wonder and tests out bizarre ways to recapture his youth! 🎈😂",
        "question": "What hobby keeps your inner child alive? Share with us! 🎮",
        "tags": "#childlikewonder #nevergrowup #innerchild #curiosity"
    },
    28: {
        "hook": "Sheldon and Amy build the most elaborate living room carpet fort in television history! 🏰🤣",
        "question": "Who else built epic living room forts as a kid? Drop a ⛺ below!",
        "tags": "#blanketfort #carpetfort #livingroomfort #childhoodvibes"
    },
    29: {
        "hook": "Raj moves into Sheldon's old apartment room, and Sheldon's territorial instincts go haywire! 🛋️😂",
        "question": "Whose side were you on: Sheldon protecting his old spot, or Raj needing a place? 🏠",
        "tags": "#rajeshkoothrappali #spotstolen #apartmenthunt #roommates"
    },
    30: {
        "hook": "Sheldon's legendary obsession with model trains and real locomotives reaches peak insanity! 🚂💨🤣",
        "question": "Is Sheldon's love for trains the purest thing in the entire series? Choo-choo! 🚆",
        "tags": "#trainenthusiast #modeltrains #conductorlife #choochoo"
    },
    31: {
        "hook": "Penny reveals huge news, but Sheldon is so focused on his own world he completely misses the room! 🤦‍♀️😅",
        "question": "Classic Sheldon: completely oblivious or just hyper-focused? Tell us below! 💭",
        "tags": "#pennyhofstadter #bigsurprises #oblivious #friendsdrama"
    },
    32: {
        "hook": "Sheldon goes to extreme lengths to avoid being captured on camera, looking like an international spy! 🕶️📸😂",
        "question": "Are you photogenic or do you dodge cameras just like Sheldon? 🤳",
        "tags": "#camerashy #dodgingcameras #spymode #secretidentity"
    },
    33: {
        "hook": "Sheldon proudly assumes Beverly flew across the country just to visit him... and the reality hits hard! ✈️🤣",
        "question": "Sheldon and Beverly's bond is so weirdly wholesome. Best mother-son dynamic that isn't biological! ❤️",
        "tags": "#beverlyandsheldon #unlikelyduo #intellectualbonds #sitcomfavs"
    },
    34: {
        "hook": "Sheldon is torn between strictly obeying the law and standing by his friends. His moral crisis is hilarious! ⚖️🤣",
        "question": "Would you break a small rule to save a close friend? What would Sheldon do? 🚨",
        "tags": "#rulefollower #lawvsfriendship #moralcrisis #sheldonrules"
    },
    35: {
        "hook": "Sheldon achieves a monumental milestone and insists on sharing the spotlight with Amy! 🏆🥰",
        "question": "Proof that behind the quirks, Sheldon Cooper has a golden heart. Who was cutting onions here? 🥺",
        "tags": "#scientificglory #shamycouple #sharingthestage #proudmoment"
    },
    36: {
        "hook": "Sheldon reveals his 50-year master plan for every second of his life. Spontaneity is strictly forbidden! 📅🤣",
        "question": "Are you a master planner like Sheldon or a chaotic go-with-the-flow type? 🧭",
        "tags": "#masterplanner #lifeschedule #colorcoded #strictlybusiness"
    },
    37: {
        "hook": "During their own wedding ceremony, Sheldon and Amy get struck by scientific genius: Super Asymmetry! 💍😲",
        "question": "Only Sheldon and Amy could pause their wedding vows for theoretical physics! Iconic! 🔬✨",
        "tags": "#shamywedding #superasymmetry #nobelprize #physicswedding"
    },
    38: {
        "hook": "Big brother Georgie visits, showing just how much he secretly protected Sheldon growing up! 🤠❤️",
        "question": "Georgie Cooper is such an incredible character. Who loves Young Sheldon as much as TBBT? 📺",
        "tags": "#georgiecooper #cooperbrothers #brotherlylove #texasroots"
    },
    39: {
        "hook": "Penny admits that despite all the madness and knocking, Sheldon is genuinely one of her favorite people! 🥹✨",
        "question": "The Sheldon & Penny sibling dynamic is the true backbone of the show. Rate their friendship! 🌟",
        "tags": "#sheldonandpenny #bestfriendgoals #knockknockknockpenny #platonicduo"
    },
    40: {
        "hook": "Beverly and Penny become best buddies over drinks, and Leonard's brain completely short-circuits! 🍸🤯🤣",
        "question": "Leonard watching his wife bond with his traumatizing mother is comedy perfection! 💀",
        "tags": "#girlstalk #motherinlawbonding #leonardshocked #unlikelyfriends"
    },
    41: {
        "hook": "Sheldon meets Amy's neurobiology colleagues for the first time... and holds nothing back! 🧠🤣",
        "question": "Would you ever introduce Sheldon Cooper to your coworkers? What would happen? 💼😅",
        "tags": "#colleaguemeeting #firstimpressions #neurobiology #zerofilter"
    },
    42: {
        "hook": "Sheldon literally pays Stuart cash money to escort Amy shopping so he can avoid the mall! 💳🛍️😂",
        "question": "Work smarter, not harder! What's the best life hack Sheldon ever pulled? 💡",
        "tags": "#shoppingday #outsourcing #stuartforhire #mallphobia"
    },
    43: {
        "hook": "Sheldon and Amy host friends in their shared apartment for the very first time. The party rules are wild! 🎈🤣",
        "question": "Would you survive a party hosted by Sheldon Cooper? Check the guest agreement first! 📜",
        "tags": "#dinnerparty #hostingoftheyear #partyguidelines #shamyapartment"
    },
    44: {
        "hook": "Sheldon's mother and Amy's parents meet each other, and the cultural clash is legendary! 🤝😂",
        "question": "Mary Cooper vs. Mrs. Fowler: Who had the better zingers in this showdown? 💥",
        "tags": "#inlawsmeeting #familyclash #marycooper #mrsfowler"
    },
    45: {
        "hook": "Sheldon surprises everyone by whispering genuine romantic lines to Amy. Nobody saw this coming! 🌹🥰",
        "question": "Who said Sheldon isn't romantic? Drop your favorite Shamy moment below! 💕",
        "tags": "#romanticwords #shamyromance #softsheldon #truelove"
    },
    46: {
        "hook": "Never enter a battle of wits with Sheldon Cooper... you will lose in under 30 seconds! ⚔️🧠😂",
        "question": "Has anyone ever won a factual debate against Sheldon without tricking him? Name the episode! 📚",
        "tags": "#debatechampion #unbeatablelogic #bazingamoment #intellectualburn"
    },
    47: {
        "hook": "Amy achieves something incredible, and Sheldon puts on his best 'I'm totally supportive' fake smile! 😬🤣",
        "question": "That forced smile will forever be etched in comedy history! Tag a friend who smiles like this! 🏷️",
        "tags": "#forcedsmile #supportivepartner #jealoussheldon #fakesmiles"
    },
    48: {
        "hook": "Sheldon's scheme to raise funding for his scientific research takes an absurdly comical turn! 💰🔬😂",
        "question": "What's the craziest scientific experiment Sheldon and the guys ever tried to fund? 🚀",
        "tags": "#fundraising #sciencefunding #schemes #grantmoney"
    },
    49: {
        "hook": "Sheldon and Amy try a sensory deprivation floatation tank for stress relief... with chaotic results! 🧖‍♂️🛁🤣",
        "question": "Would you ever try a floatation tank, or are you terrified like Sheldon? 🌊",
        "tags": "#floatationtank #sensorydeprivation #stressrelief #meditationfail"
    },
    50: {
        "hook": "Sheldon shows his genuine appreciation for his group of friends and Amy in his own eccentric way! 🍕❤️",
        "question": "The gang wouldn't be the gang without Sheldon Cooper. Who is your absolute ride-or-die friend? 🫂",
        "tags": "#squadgoals #friendshipcircle #groupappreciation #sitcomfamily"
    },
    51: {
        "hook": "Sheldon works himself into a full-blown existential anxiety spiral over an unsolved physics equation! 🌀🤯",
        "question": "Every student during finals week relates to Sheldon Cooper right here! Agree? 📚☕",
        "tags": "#anxietymode #overthinking #finalsweek #physicsstruggle"
    },
    52: {
        "hook": "Sheldon tries to 'relax' like a normal human being, and it turns out to be more stressful than work! 🧘‍♂️🤣",
        "question": "How do you relax after a long week? Yoga, video games, or binge-watching TBBT? 🎮🍿",
        "tags": "#tryingtochill #relaxfail #uptight #howtounwind"
    },
    53: {
        "hook": "Sheldon kept a major secret hidden from Amy for years, and the moment he confesses is priceless! 🤫😂",
        "question": "Could you have kept this secret from your partner for that long? Spill the beans! ☕",
        "tags": "#bigsecret #confessiontime #shamysecrets #truthcomesout"
    },
    54: {
        "hook": "Leonard admits he kind of misses 'bad-boy' rule-breaking Sheldon... until real life strikes! 🕶️🏍️🤣",
        "question": "Bad boy Sheldon Cooper vs Regular Sheldon: Which version was funnier? ⚡",
        "tags": "#badboysheldon #leatherjacket #rebelwithoutacause #roommatedrama"
    },
    55: {
        "hook": "Sheldon drops a bomb of brutal honesty on Penny that leaves her completely speechless! 💣😳🤣",
        "question": "Penny's facial expressions when Sheldon talks are unmatched! Drop a 😂 if this cracked you up!",
        "tags": "#brutalhonesty #sheldonquotes #pennystunned #sitcomburns"
    },
    56: {
        "hook": "Leonard and Penny hold a solemn, candlelit funeral for Sheldon's disproven scientific theory! 🕯️📜😂",
        "question": "Only true friends would attend a funeral for a math paper! Best friends ever? 🤝",
        "tags": "#paperfuneral #disprovenphysics #solemnceremony #truefriendship"
    },
    57: {
        "hook": "Leonard finally snaps and launches a tactical counter-attack against Sheldon's roommate tyranny! 🎯🤣",
        "question": "How did Leonard survive living with Sheldon for 12 years? Saint Leonard! 😇",
        "tags": "#fightback #roommatewar #sheldonvsleonard #rebellion"
    },
    58: {
        "hook": "For the first time in recorded human history, Sheldon actually listens to Leonard's advice! 👂😲😂",
        "question": "Mark your calendars! The day Sheldon Cooper took advice from someone else! 📅✨",
        "tags": "#miracleoccurs #listeningtoadvice #milestonemoment #brotherhood"
    },
    59: {
        "hook": "The entire group comes together to cater to Sheldon's wildest demands... because they secretly love him! 🍰🥰",
        "question": "Does the group spoil Sheldon too much, or is he just impossible to say no to? 🤷‍♂️",
        "tags": "#spoiledsheldon #friendshipcircle #cateringtoneeds #sitcomlove"
    },
    60: {
        "hook": "Penny uses simple street-smarts to solve a complex dilemma that baffled Caltech PhDs! 💡👠😂",
        "question": "Penny proving book-smarts aren't everything will always be satisfying! Team Penny! 💅",
        "tags": "#streetsmarts #pennygenius #commonbeatsbook #girlboss"
    },
    61: {
        "hook": "Leonard wins an award, and Sheldon goes through the 5 stages of grief trying to process it! 🏅😲🤣",
        "question": "Can Sheldon ever truly be happy for Leonard's success? Answer below! 👇",
        "tags": "#jealousfriend #awardceremony #siblingrivalry #congratulations"
    },
    62: {
        "hook": "Sheldon and Penny conduct the famous psychological 36-question 'fast-fall-in-love' experiment! 🧪❤️👀",
        "question": "That 4-minute staring contest at the end... one of the greatest scenes ever filmed! Agree? 🥺",
        "tags": "#fastfallinlove #36questions #psychologyexperiment #sheldonandpenny"
    },
    63: {
        "hook": "Sheldon takes powerful cold medicine and enters an alternate dimension of delirium! 💊😵‍💫🤣",
        "question": "Sick Sheldon is legendary ('Soft Kitty, warm kitty...')! What's his funniest sickness moment? 🐱",
        "tags": "#sicksheldon #softkitty #coldmedicine #delirious"
    },
    64: {
        "hook": "Sheldon's religious Texas mother meets Leonard's cold clinical mother, and sparks immediately fly! ⚡🤣",
        "question": "Mary Cooper vs Beverly Hofstadter: The ultimate battle of opposite parenting styles! 🥊",
        "tags": "#momsclash #maryvsbeverly #parentingstyles #legendarymothers"
    },
    65: {
        "hook": "In the grand finale, Sheldon and Amy stand together as their biggest secret is revealed to the world! 🌟😭🏆",
        "question": "The ultimate full-circle moment for Sheldon Cooper! Drop a ❤️ if Big Bang Theory changed your life!",
        "tags": "#seriesfinale #nobelspeech #sheldonandamy #sitcomvaultdaily"
    }
}


def build_rich_caption(seq_num: int, title: str, clean_t: str) -> str:
    details = SCENE_DETAILS.get(seq_num, {
        "hook": f"{clean_t} 🤣",
        "question": "What was your favorite part of this scene? Let us know below! 👇",
        "tags": "#thebigbangtheory #tbbt #sheldoncooper #bazinga"
    })

    caption = (
        f"{details['hook']}\n\n"
        f"💬 {details['question']}\n\n"
        f"👉 Follow @sitcomvaultdaily for daily Big Bang Theory & comedy gold! 🍿😂\n"
        f"Double-tap if this made your day! ❤️\n\n"
        f"•\n•\n•\n"
        f"{details['tags']} #reels #reelsinstagram #comedyreels #sitcom #funnyreels #viralreels #explorepage #tvshowclips #sitcomvaultdaily"
    )
    return caption


def run():
    print("=" * 70)
    print("  GENERATING RICH DESCRIPTIONS & DAILY SCHEDULES (1 TO 65)")
    print("=" * 70)

    with open(TBBT_MANIFEST, "r", encoding="utf-8") as f:
        tbbt_data = json.load(f)

    # 1. Update manifest with rich descriptions
    for item in tbbt_data.get("shorts", []):
        seq = item.get("sequence", 1)
        title = item.get("title", "")
        clean_t = item.get("clean_title", title)
        item["rich_description"] = build_rich_caption(seq, title, clean_t)

    with open(TBBT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(tbbt_data, f, indent=2, ensure_ascii=False)
    print(f"[1/3] Updated TBBT manifest with 65 rich descriptions: {TBBT_MANIFEST}")

    # 2. Update instagram_queue.json
    start_date = datetime.now() + timedelta(days=1)
    start_date = start_date.replace(hour=19, minute=30, second=0, microsecond=0)

    queue_items = []
    q_idx = 1

    # Add 65 TBBT shorts sequenced 1 to 65
    for s in tbbt_data.get("shorts", []):
        seq = s.get("sequence", q_idx)
        sched_dt = start_date + timedelta(days=q_idx - 1)
        caption = s.get("rich_description") or build_rich_caption(seq, s["title"], s.get("clean_title", s["title"]))

        queue_items.append({
            "queue_index": q_idx,
            "id": s["id"],
            "show": "The Big Bang Theory",
            "local_path": s["local_path"],
            "file_name": s["file_name"],
            "title": s.get("clean_title", s["title"]),
            "caption": caption,
            "status": "pending",
            "scheduled_for": sched_dt.strftime("%Y-%m-%d %H:%M"),
            "instagram_media_id": None,
            "instagram_code": None,
            "instagram_url": None,
            "posted_at": None
        })
        q_idx += 1

    # Also keep HIMYM items from previous queue if present
    himym_dir = MEDIA_BASE / "himym"
    himym_manifest = himym_dir / "manifest.json"
    if himym_manifest.exists():
        with open(himym_manifest, "r", encoding="utf-8") as f:
            h_data = json.load(f)
        for h in h_data.get("shorts", []):
            lp = Path(h.get("local_path", ""))
            if lp.exists() and lp.suffix.lower() == ".mp4":
                sched_dt = start_date + timedelta(days=q_idx - 1)
                t = h.get("title", "Legendary HIMYM Moment")
                caption = (
                    f"{t} 🍻😂\n\n"
                    f"💬 What's your all-time favorite How I Met Your Mother scene? Drop it below! 👇\n\n"
                    f"👉 Follow @sitcomvaultdaily for legendary HIMYM & sitcom moments! 🍺🍿\n"
                    f"Double tap if this made you laugh! ❤️\n\n"
                    f"•\n•\n•\n"
                    f"#himym #howimetyourmother #barneystinson #tedmosby #legendary #comedyreels #sitcom #viralreels #explorepage #sitcomvaultdaily"
                )
                queue_items.append({
                    "queue_index": q_idx,
                    "id": h["id"],
                    "show": "How I Met Your Mother",
                    "local_path": str(lp),
                    "file_name": lp.name,
                    "title": t,
                    "caption": caption,
                    "status": "pending",
                    "scheduled_for": sched_dt.strftime("%Y-%m-%d %H:%M"),
                    "instagram_media_id": None,
                    "instagram_code": None,
                    "instagram_url": None,
                    "posted_at": None
                })
                q_idx += 1

    full_queue = {
        "channel": "@sitcomvaultdaily",
        "total_items": len(queue_items),
        "pending_items": sum(1 for x in queue_items if x["status"] == "pending"),
        "posted_items": 0,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "queue": queue_items
    }

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(full_queue, f, indent=2, ensure_ascii=False)
    print(f"[2/3] Updated Instagram Queue with {len(queue_items)} items: {QUEUE_FILE}")

    # 3. Export to meta_business_suite_schedule.csv
    csv_rows = []
    for item in queue_items:
        csv_rows.append({
            "Index": item["queue_index"],
            "Show": item["show"],
            "File": item["file_name"],
            "Path": item["local_path"],
            "Title": item["title"],
            "Scheduled_Date_Time": item["scheduled_for"],
            "Caption": item["caption"]
        })

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Index", "Show", "File", "Path", "Title", "Scheduled_Date_Time", "Caption"])
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"[3/3] Exported CSV Schedule: {CSV_FILE}")

    print("\n" + "=" * 70)
    print("🎉 DESCRIPTIONS & SCHEDULE FULLY BUILT!")
    print(f"   First video:  {queue_items[0]['file_name']} -> {queue_items[0]['scheduled_for']}")
    print(f"   Last TBBT:    {queue_items[64]['file_name']} -> {queue_items[64]['scheduled_for']}")
    print(f"   Total Videos: {len(queue_items)} (65 TBBT in exact YouTube sequence + 50 HIMYM)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
