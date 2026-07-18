from aoep_shared.live_room_games import (
    ANSWER_RACE_TYPES,
    GAME_LIBRARY,
    apply_action,
    public_game,
    start_game,
)


def test_library_has_at_least_twelve_playable_games():
    assert len(GAME_LIBRARY) >= 12
    assert len({game["id"] for game in GAME_LIBRARY}) == len(GAME_LIBRARY)
    for game_type in ANSWER_RACE_TYPES:
        game = start_game(game_type, prompt="Course question", answer="correct")
        event = apply_action(
            game, participant_id="a", participant_name="Ada", answer="correct",
        )
        assert event["points"] == 25


def test_quiz_race_only_first_correct_wins():
    game = start_game("quiz_race", prompt="AI?", answer="artificial intelligence", points=25)
    wrong = apply_action(game, participant_id="a", participant_name="Ada", answer="robots")
    assert wrong["correct"] is False
    win = apply_action(
        game, participant_id="b", participant_name="Grace",
        answer="Artificial Intelligence",
    )
    assert win["points"] == 25
    assert game["winner_name"] == "Grace"
    assert "_answer" not in public_game(game)


def test_tic_tac_toe_requires_correct_answer_then_places_mark():
    game = start_game("tic_tac_toe", prompt="ML?", answer="machine learning")
    apply_action(
        game, participant_id="a", participant_name="Ada",
        answer="machine learning", cell=0,
    )
    assert game["board"][0] == "X"
    assert game["turn"] == "O"


def test_hangman_masks_answer_and_finishes():
    game = start_game("hangman", prompt="Training material", answer="data")
    for letter in "dat":
        apply_action(
            game, participant_id="a", participant_name="Ada", letter=letter,
        )
    assert game["status"] == "won"
    assert "_" not in public_game(game)["masked"]
