"""Family meal planner — Hyderabadi-tuned, iron-aware, kid-friendly.

Suggests two menu options per slot (adult breakfast, kid breakfast,
dinner) per day. Dinner doubles as next-day lunch. Persists history so
the same dish doesn't repeat within ~7 days, then rotates back.

Design notes:
  - Wife has iron deficiency → planner biases toward iron-rich dals
    (palak dal, methi dal), aamla rasam, leafy greens at least 3x/week.
  - Daughter (3.5y) gets a fresh probiotic-leaning breakfast (idly/dosa/
    uttapam with chutneys) every morning, separate from adult menu.
  - Husband eats egg whites — appears in adult breakfast rotation.
  - Bone broth (Paya) included as occasional weekend option.
  - Bottle gourd / ridge gourd / drumstick / gutti vankaya etc. included
    as Andhra/Hyderabadi vegetable curries the family already eats.
"""
