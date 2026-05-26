# =============================================================================
# constants.py
# Global constants, color palette, layout geometry, and game tuning values.
# Keeping all magic numbers here makes balancing and reskinning trivial.
# =============================================================================

# ---------------------------------------------------------------------------
# Screen / Display
# ---------------------------------------------------------------------------
SCREEN_W = 1280
SCREEN_H = 720
FPS      = 60
TITLE    = "Limbic Journey"

# ---------------------------------------------------------------------------
# Layout anchors  (computed from screen dimensions so resizing is one edit)
# ---------------------------------------------------------------------------
HUD_H         = 58          # top bar
CHOICE_BAR_H  = 84          # bottom choice area
CONTENT_TOP   = HUD_H
CONTENT_BOT   = SCREEN_H - CHOICE_BAR_H
CONTENT_H     = CONTENT_BOT - CONTENT_TOP   # 578 px

MEMORY_PANEL_W = 310        # right sidebar
EVENT_PANEL_W  = SCREEN_W - MEMORY_PANEL_W  # 970 px

# ---------------------------------------------------------------------------
# Colour Palette
# Philosophy: deep neural-purple base; warm amber for emotion;
# cool grey for neutral; red for danger; green for safe; gold for LTM.
# ---------------------------------------------------------------------------
C = {
    # Background layers
    "bg":           (12,  14,  26),
    "bg_night":     ( 6,   6,  18),   # deeper indigo for night phase
    "bg_travel":    (16,  12,  10),   # dark earthy tone for travel phase
    "bg_panel":     (20,  22,  40),
    "bg_dark":      ( 8,   9,  18),
    "bg_card":      (28,  32,  52),
    "bg_card_alt":  (34,  38,  60),

    # Text
    "text":         (220, 220, 235),
    "text_dim":     (130, 130, 155),
    "text_bright":  (255, 255, 255),
    "text_warn":    (255, 200,  80),

    # HUD accents
    "health_full":  ( 80, 210, 120),
    "health_mid":   (220, 180,  50),
    "health_low":   (210,  60,  60),
    "health_bg":    ( 40,  45,  65),

    # Memory type colours
    "stm":          ( 90, 140, 220),     # short-term: cool blue
    "ltm":          (200, 165,  40),     # long-term: gold
    "emotional":    (200,  80, 120),     # emotional: rose
    "uncertain":    (160, 100, 200),     # uncertain: purple
    "false":        (200,  60,  60),     # false memory: red
    "fading":       ( 80,  80, 100),     # fading: dim grey
    "dream":        (140, 110, 220),     # dream replay: soft violet

    # Category colours (event / memory tag)
    "cat_danger":   (210,  60,  60),
    "cat_food":     ( 80, 200, 100),
    "cat_neutral":  (130, 145, 170),
    "cat_sensory":  ( 80, 190, 210),
    "cat_emotional":(200,  90, 140),
    "cat_ambiguous":(170, 130,  80),
    "cat_contextual":(120,170, 200),

    # UI chrome
    "border":       ( 60,  68, 100),
    "border_focus": (120, 140, 210),
    "border_hot":   (200, 165,  40),
    "shadow":       (  0,   0,   0),

    # Buttons
    "btn":          ( 40,  48,  78),
    "btn_hover":    ( 55,  65, 100),
    "btn_press":    ( 30,  36,  60),
    "btn_disabled": ( 30,  34,  50),
    "btn_positive": ( 40,  90,  60),
    "btn_positive_hover": (55, 115, 80),
    "btn_danger":   ( 90,  35,  35),
    "btn_danger_hover":   (120, 50, 50),
    "btn_gold":     ( 90,  75,  25),
    "btn_gold_hover":(120, 100, 35),

    # Overlays
    "overlay":      (  0,   0,   0),     # used at partial alpha
    "journal_bg":   ( 10,  12,  22),
    "merge_glow":   (200, 165,  40),

    # Misc
    "white":        (255, 255, 255),
    "black":        (  0,   0,   0),
    "transparent":  (  0,   0,   0),     # used with colorkey
}

# ---------------------------------------------------------------------------
# Font size constants  (actual Font objects are lazy-loaded via fonts.py)
# ---------------------------------------------------------------------------
FS_TITLE   = 42
FS_HEADING = 28
FS_BODY    = 18
FS_LABEL   = 15
FS_SMALL   = 13
FS_MONO    = 14

# ---------------------------------------------------------------------------
# Game Balance  (tweak here, code reads from these)
# ---------------------------------------------------------------------------
BAL = {
    "stm_capacity":            7,     # max short-term memories per day
    "consolidation_slots":     4,     # memories player may push to LTM per night
    "dream_replay_count":      1,     # auto-reinforced STM slots per night
    "events_per_day":          5,
    "memory_decay_per_night":  0.18,  # fraction of strength lost if not consolidated
    "emotional_decay_resist":  0.40,  # emotional memories lose less strength
    "consolidation_boost":     0.30,  # strength gained by consolidating
    "repeat_exposure_boost":   0.15,  # strength gained per repeat encounter
    "false_memory_risk_low":   0.30,  # confidence threshold for risky merges
    "merge_trait_threshold":   0.40,  # min confidence to begin trait merge
    "mastery_max_exposure":    5,     # exposures to reach max mastery
    "travel_health_max":       100,
    "travel_health_start":     80,
    "bad_recall_damage":       15,
    "good_recall_heal":        8,
    "no_memory_damage":        20,
    "total_nights":            5,

    # Forgetting curve (Ebbinghaus) — decay scales by memory age
    "decay_fresh_mult":        1.6,   # 0-night-old memories decay faster
    "decay_one_night_mult":    1.0,
    "decay_two_nights_mult":   0.75,
    "decay_old_mult":          0.50,  # 3+ night-old memories decay slowly

    # Spaced repetition
    "spaced_rep_gap":          3,     # nights apart required for bonus
    "spaced_rep_bonus":        0.08,  # extra strength boost on spaced recall

    # Interference (similar traits lower confidence on both memories)
    "interference_penalty":    0.05,

    # Reconsolidation (memory use slightly destabilises the trace)
    "reconsolidation_conf_drop":    0.04,
    "reconsolidation_mutate_chance": 0.10,

    # Cortisol — high-stress encoding (health ≤ threshold)
    "cortisol_threshold":      30,
    "cortisol_encode_penalty": 0.30,   # non-emotional memories encoded weaker
    "cortisol_emotional_boost": 0.50,  # emotional memories encoded stronger

    # Probabilistic LTM consolidation
    "ltm_base_chance":         0.70,
    "ltm_danger_bonus":        0.25,   # danger-category memories consolidate easier
    "ltm_mnemonic_bonus":      0.20,   # mnemonic-encoded memories consolidate easier

    # Mnemonic encoding
    "mnemonic_decay_mult":     0.40,   # fraction of normal decay rate

    # Context-dependent retrieval
    "context_mismatch_debuff": 0.20,   # strength penalty for mismatched scene

    # Semantic graduation (episodic → semantic after enough reinforcement)
    "semantic_graduation_threshold": 4,
}

# ---------------------------------------------------------------------------
# Progression Phases
# ---------------------------------------------------------------------------
PHASE_CONFIG = {
    "early":  {"nights": (1, 2),  "label": "Encoding",      "colour": (90, 140, 220)},
    "mid":    {"nights": (3, 3),  "label": "Reinforcement",  "colour": (80, 190, 140)},
    "late":   {"nights": (4, 5),  "label": "Mastery",        "colour": (200, 165, 40)},
}

# ---------------------------------------------------------------------------
# Animation timings  (seconds)
# ---------------------------------------------------------------------------
ANIM = {
    "card_fly_dur":     0.35,
    "fade_dur":         0.45,
    "pulse_period":     1.20,
    "consolidate_dur":  0.60,
    "result_hold":      1.80,
}

# ---------------------------------------------------------------------------
# Z-order layers
# ---------------------------------------------------------------------------
LAYER_BG      = 0
LAYER_PANELS  = 10
LAYER_CONTENT = 20
LAYER_HUD     = 30
LAYER_OVERLAY = 40
LAYER_TOOLTIP = 50
