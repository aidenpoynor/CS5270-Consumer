import logging

logger = logging.getLogger(__name__)

class RequestProcessor:
    def __init__(self, store):
        self.store = store


    def process(self, request):
        logger.info(f"Processing {request.type} request {request.request_id} for widget {request.widget_id}")
        if request.type == "create":
            self.store.create(request)
        elif request.type == "update":
            self.store.update(request)
        elif request.type == "delete":
            self.store.delete(request)
        else:
            logger.warning(f"Unknown request type '{request.type}'; skipping request {request.request_id}")
