import json

from openai import OpenAI


class HeadlineImageMatcher:
    def __init__(self, api_key: str):
        """
        Initialize the HeadlineImageMatcher with OpenAI API key.
        Args:
            api_key (str): OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)

    def load_headlines(self, file_path: str) -> list[str]:
        """
        Load headlines from a file.
        Args:
            file_path (str): Path to the file containing headlines
        Returns:
            List[str]: List of headlines
        """
        try:
            with open(file_path) as file:
                return json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"The file {file_path} was not found.")
        except json.JSONDecodeError:
            raise ValueError(f"The file {file_path} contains invalid JSON.")

    def load_image_data(self, file_path: str) -> list[dict[str, str]]:
        """
        Load image data containing locations and descriptions.
        Args:
            file_path (str): Path to the image data JSON file
        Returns:
            List[Dict[str, str]]: List of image data dictionaries
        """
        try:
            with open(file_path) as file:
                return json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"The file {file_path} was not found.")
        except json.JSONDecodeError:
            raise ValueError(f"The file {file_path} contains invalid JSON.")

    def find_best_matching_image(self, headline: str, image_data: list[dict[str, str]]) -> str:
        """
        Find the best matching image for a headline using GPT-4.
        Args:
            headline (str): The headline text
            image_data (List[Dict[str, str]]): List of image data dictionaries
        Returns:
            str: Path to the best matching image
        """
        descriptions = "\n".join(
            [
                f"{i + 1}. Description: {img['description']}\nLocation: {img['location']}"
                for i, img in enumerate(image_data)
            ]
        )

        prompt = f"""Given the following image descriptions and a news headline, determine which image would be most appropriate.

Headline: "{headline}"

Available images:
{descriptions}

Return ONLY the image location path that best matches the headline, nothing else. The path should start with 'examples/election/src/election_sim/img/."""

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an image matching assistant. Select the most appropriate image location based on the headline and available image descriptions.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            if completion.choices[0].message.content != None:
                matched_path = completion.choices[0].message.content.strip()

            if all(img["location"] != matched_path for img in image_data):
                return image_data[17]["location"]
            return matched_path

        except Exception as e:
            print(f"Error matching image for headline '{headline}': {e!s}")
            return image_data[17]["location"]

    def create_headline_image_mapping(
        self, headlines: list[str], image_data: list[dict[str, str]]
    ) -> dict[str, list[str]]:
        """
        Create a mapping of headlines to lists of image paths.
        Args:
            headlines (List[str]): List of headlines
            image_data (List[Dict[str, str]]): List of image data dictionaries
        Returns:
            Dict[str, List[str]]: Dictionary mapping headlines to lists of image paths
        """
        mapping = {}
        for headline in headlines:
            try:
                image_path = self.find_best_matching_image(headline, image_data)
                # Store the image path in a list
                mapping[headline] = [image_path]
            except Exception as e:
                print(f"Error processing headline '{headline}': {e!s}")
                mapping[headline] = [image_data[0]["location"]]
        return mapping

    def save_mapping(self, mapping: dict[str, list[str]], output_file: str):
        """
        Save the headline-image mapping to a JSON file.
        Args:
            mapping (Dict[str, List[str]]): Dictionary mapping headlines to lists of image paths
            output_file (str): Path to save the output JSON file
        """
        try:
            with open(output_file, "w") as file:
                json.dump(mapping, file, indent=2)
        except Exception as e:
            raise Exception(f"Error saving mapping to file: {e!s}")


def main():
    # Your API key
    api_key = ""
    if not api_key:
        raise ValueError("Please provide a valid OpenAI API key")

    matcher = HeadlineImageMatcher(api_key)

    try:
        headlines = matcher.load_headlines(
            "/Users/gayatrikrishnakumar/Documents/mastodon-sim/examples/election/src/election_sim/cached_headlines.json"
        )  # add complete path
        image_data = matcher.load_image_data(
            "/Users/gayatrikrishnakumar/Documents/mastodon-sim/examples/election/src/election_sim/image_data.json"
        )  # add complete path

        mapping = matcher.create_headline_image_mapping(headlines, image_data)

        matcher.save_mapping(
            mapping,
            "/Users/gayatrikrishnakumar/Documents/mastodon-sim/examples/election/src/election_sim/image_repo.json",
        )  # add complete path

        print("Successfully created headline-image mapping!")
        print(f"Total headlines processed: {len(mapping)}")

    except Exception as e:
        print(f"Error: {e!s}")


if __name__ == "__main__":
    main()
