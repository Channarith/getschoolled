#!/usr/bin/env python3
"""Salareen film - "The Evolution of Learning".

Opens on the 200-year-old classroom model and the global learning crisis
($21T / 70% can't read), then resolves into the adaptive AI tutor and the
"we multiply great teachers" message (44M teacher gap). Realistic AI cast,
cinematic Ken Burns + crossfades, captions read with sound off.

Output: docs/demos/salareen_evolution_of_learning.mp4
"""
import os

import promo_lib as P

OUT = os.path.join(P.DEMOS, "salareen_evolution_of_learning.mp4")
C = P.C

SHOTS = [
    dict(img="actors/ev1_classroom_1825.png", z0=1.05, z1=1.15, px=0.2, py=0.1,
         kicker="SINCE 1825", line="One teacher.", line2="Thirty different minds.",
         accent=C["gold"], darken=0.10),
    dict(img="actors/ev2_empty_classroom.png", z0=1.14, z1=1.04, px=-0.2, py=0.1,
         kicker="THE COST OF ONE-SIZE-FITS-ALL", line="A $21 trillion crisis.",
         line2="70% of kids can't read a simple story.",
         source="World Bank / UNESCO, 2022", accent=C["red"], sat=0.85, line_size=58),
    dict(img="actors/ev3_child_tablet_teacher.png", z0=1.06, z1=1.16, px=0.3, py=0.1,
         kicker="THE NEXT EVOLUTION", line="What if every child had",
         line2="a patient teacher of their own?", accent=C["mint"], line_size=58),
    dict(img="actors/ev4_teacher_multiplied.png", z0=1.15, z1=1.05, px=0.2, py=-0.1,
         kicker=None, line="We don't replace teachers.",
         line2="We multiply the great ones.",
         source="The world is short 44M teachers. — UNESCO, 2024",
         accent=C["brand"], line_size=58),
]

if __name__ == "__main__":
    P.run_photo_film(
        SHOTS, OUT,
        end_tagline="The next evolution of learning.",
        end_url="salareen.com",
        shot_dur=170, xf=20, end_dur=160, end_xf=20,
    )
