#!/usr/bin/env python3
"""Salareen film - "The 20-Minute Expert" (corporate / B2B).

Leads with the forgetting curve (research suggests up to ~90% of new training
is gone within a week) and resolves with Salareen's spaced-repetition retention:
short to finish, but it actually sticks. Realistic AI cast, cinematic motion,
captions read with sound off.

Output: docs/demos/salareen_20_minute_expert.mp4
"""
import os

import promo_lib as P

OUT = os.path.join(P.DEMOS, "salareen_20_minute_expert.mp4")
C = P.C

SHOTS = [
    dict(img="actors/tm3_oldway_binders.png", z0=1.05, z1=1.15, px=0.2, py=0.1,
         kicker="THE PROBLEM WITH TRAINING", line="Most of it is forgotten —",
         line2="up to 90% within a week.",
         source="Research: Ebbinghaus; Murre & Dros, 2015",
         accent=C["red"], sat=0.8, darken=0.08, line_size=58),
    dict(img="actors/tm1_desk_finish.png", z0=1.14, z1=1.04, px=-0.2, py=0.0,
         chip="20-MINUTE EXPERT", line="Her compliance course?",
         line2="Twenty minutes.", accent=C["mint"], line_size=60),
    dict(img="actors/tm2_meeting_later.png", z0=1.06, z1=1.16, px=0.25, py=0.1,
         kicker="THREE WEEKS LATER", line="She still knows",
         line2="exactly what to do.", accent=C["brand"], line_size=60, disc=True),
    dict(img="actors/tm4_team_manager.png", z0=1.15, z1=1.05, px=0.2, py=-0.1,
         chip="SALAREEN FOR TEAMS", line="Spaced, quizzed, reinforced —",
         line2="so it actually sticks.",
         source="Spaced repetition: Cepeda et al., 2006",
         accent=C["gold"], line_size=56),
]

if __name__ == "__main__":
    P.run_photo_film(
        SHOTS, OUT,
        end_tagline="Training your team finishes — and remembers.",
        end_url="salareen.com/teams",
        shot_dur=165, xf=20, end_dur=160, end_xf=20,
    )
