class Agent:
    """
    An agent class for an exogenous (i.e. fixed/external to the sim) posting schedule and content
    """

    def __init__(self, name, app, posts):
        self._agent_name = name
        self.app = app
        self.posts = posts
        self.used_posts = set()
        self.current_post_index = 0
        self.seed_post = ""

    def post(self):
        post = self.generate_post()
        media = [img_filepath for img_filepath in self.posts[post]]
        if len(media) > 0:
            self.app.post_toot(self.name, status=post, media_links=media)
        else:
            self.app.post_toot(self.name, status=post)
        return post

    def generate_post(self):
        # Get next unused post
        while self.current_post_index < len(self.posts):
            post = list(self.posts.keys())[self.current_post_index]
            self.current_post_index += 1
            if post not in self.used_posts:
                self.used_posts.add(post)
                return post

        # Reset if we've gone through all posts
        self.current_index = 0
        self.used_posts.clear()
        return self.posts[0]  # Start over with first post
