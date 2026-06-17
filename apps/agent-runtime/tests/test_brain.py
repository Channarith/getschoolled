from agent_runtime.brain import TeachingBrain
from orchestrator.director import ClassContext, LessonState


def test_brain_narrates_by_default():
    brain = TeachingBrain()
    action = brain.step(ClassContext(slides_total=10, slide_index=1))
    assert action.kind == "narrate"
    assert action.state is LessonState.TEACHING


def test_brain_answers_when_question_pending():
    brain = TeachingBrain()
    action = brain.step(
        ClassContext(slides_total=10, slide_index=1, pending_questions=2)
    )
    assert action.kind == "answer"


def test_brain_ends_when_finished():
    brain = TeachingBrain()
    action = brain.step(ClassContext(slides_total=3, slide_index=3, pending_questions=0))
    assert action.kind == "end"
    assert action.state is LessonState.DONE


def test_brain_has_a_provider_factory():
    brain = TeachingBrain()
    assert brain.factory.config.deploy_mode.value in {"local", "cloud"}
