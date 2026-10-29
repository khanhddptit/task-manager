from flask_socketio import emit

def init_sockets(socketio):
    @socketio.on("subscribe_notifications")
    def handle_subscribe(data):
        user_id = data.get("user_id")
        if user_id:
            from flask_socketio import join_room
            join_room(f"notifications_{user_id}")

    @socketio.on("disconnect")
    def handle_disconnect():
        pass
