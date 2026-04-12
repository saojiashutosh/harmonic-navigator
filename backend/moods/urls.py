from .views import (
    MoodSessionViewSet,
    QuestionViewSet,
    AnswerViewSet,
    MoodInferenceViewSet,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'mood-sessions', MoodSessionViewSet, basename='mood-session')
router.register(r'questions', QuestionViewSet, basename='question')
router.register(r'answers', AnswerViewSet, basename='answer')
router.register(r'mood-inferences', MoodInferenceViewSet,
                basename='mood-inference')

urlpatterns = []
urlpatterns = urlpatterns + router.urls
