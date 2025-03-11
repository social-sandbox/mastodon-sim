import concurrent.futures
import datetime


# NA - object to represent a scheduled news agents that can post toots on a schedule
class Agent:
    def __init__(self, name, mastodon_username, mastodon_app, post_schedule, posts):
        self.name = name
        self.mastodon_username = mastodon_username
        self.mastodon_app = mastodon_app
        self.post_schedule = post_schedule
        self.posts = posts
        self.used_posts = set()
        self.current_post_index = 0

    def check_and_post(self, current_time):
        """Check if should post based on current time and post if needed"""
        for scheduled_time in self.post_schedule:
            if (
                scheduled_time.hour == current_time.hour
                and scheduled_time.minute == current_time.minute
            ):
                post = self.generate_post()

                media = [img_filepath for img_filepath in self.posts[post]]

                if len(media) > 0:
                    self.mastodon_app.post_toot(
                        self.mastodon_username, status=post, media_links=media
                    )
                else:
                    self.mastodon_app.post_toot(self.mastodon_username, status=post)
                return True
        return False

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


# NA write post seed toots function for the news agent
def post_seed_toots_news_agents(news_agent, mastodon_apps):
    # Parallelize the loop using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit tasks for each news agent
        futures = [
            executor.submit(
                lambda agent=n_agent: (
                    mastodon_apps[n_agent["name"]].post_toot(
                        n_agent["mastodon_username"], status=n_agent["seed_toot"]
                    )
                    if n_agent["seed_toot"] and n_agent["seed_toot"] != "-"
                    else None
                )
            )
            for n_agent in news_agent
        ]

        # Optionally, wait for all tasks to complete
        for future in concurrent.futures.as_completed(futures):
            future.result()  # This will raise any exceptions that occurred in the thread, if any


# NA getting post times for the news agent
def get_post_times_news_agent(news_agent):
    news_agent_datetimes = {}
    for agent in news_agent:
        # Ensure the agent has the required keys
        name = agent.get("name", "Unnamed Agent")
        post_schedule = agent.get("toot_posting_schedule", [])

        try:
            # Generate datetime objects for each time in the schedule
            news_agent_datetimes[name] = [
                datetime.datetime.now().replace(
                    hour=int(post_time.split(":")[0]),
                    minute=int(post_time.split(":")[1].split()[0]),
                    second=0,
                    microsecond=0,
                )
                for post_time in post_schedule
            ]
        except ValueError as e:
            raise ValueError(f"Error processing agent '{name}': {e}")

    return news_agent_datetimes
