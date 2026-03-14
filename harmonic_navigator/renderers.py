from rest_framework.renderers import JSONRenderer


class HarmonicJsonRenderer(JSONRenderer):

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is not None:
            # status_codes = [200, 201, 204, 205]
            if renderer_context['response'].status_code in [200, 201, 205]:
                data = {'data': data, "error": {}, "isSuccess": True}
            elif renderer_context['response'].status_code == 204:
                return super(HarmonicJsonRenderer, self).render(data, accepted_media_type, renderer_context)
            else:
                if "message" not in data:
                    data = {"message": data}
                data = {'data': {}, "error": data, "isSuccess": False}
        else:
            data = {'data': data}
        return super(HarmonicJsonRenderer, self).render(data, accepted_media_type, renderer_context)
