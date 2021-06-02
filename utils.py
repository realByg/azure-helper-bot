import os

user_dict = {}


class UserDict:

    def __init__(self):
        self.email = None
        self.refresh_token = None
        self.subscription_id = None


class RefreshToken:

    def __init__(self):
        self.base_path = os.path.join(os.getcwd(), 'rtokens')
        if not os.path.exists(self.base_path):
            os.mkdir(self.base_path)

    def save(self, email: str, refresh_token: str):
        open(os.path.join(self.base_path, email), 'w').write(refresh_token)

    def list(self):
        return os.listdir(self.base_path)

    def get(self, email: str):
        return open(os.path.join(self.base_path, email), 'r').read()

    def remove(self, email: str):
        os.remove(os.path.join(self.base_path, email))
