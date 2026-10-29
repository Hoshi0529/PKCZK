import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from urllib.error import URLError
from urllib.request import Request, urlopen


def _fetch_pokemon_artwork(pokemon: str) -> tuple[str, str]:
    try:
        request = Request(
            f"https://pokeapi.co/api/v2/pokemon/{pokemon}",
            headers={"User-Agent": "pokecham/1.0"},
        )
        with urlopen(request, timeout=3) as response:
            details = json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"PokeAPIから{pokemon}の情報を取得できませんでした。"
        ) from error

    image_url = details["sprites"]["other"]["official-artwork"]["front_default"]
    if not image_url:
        raise RuntimeError(f"PokeAPIに{pokemon}の公式アート画像がありません。")

    try:
        image_request = Request(image_url, headers={"User-Agent": "pokecham/1.0"})
        with urlopen(image_request, timeout=3) as response:
            image_data = base64.b64encode(response.read()).decode("ascii")
            media_type = response.headers.get_content_type()
    except (URLError, TimeoutError) as error:
        raise RuntimeError(
            f"PokeAPIが提供する{pokemon}の画像を取得できませんでした。"
        ) from error

    return pokemon, f"data:{media_type};base64,{image_data}"


def fetch_pokemon_artwork() -> tuple[dict[str, str], list[str]]:
    artwork: dict[str, str] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        requests = [
            executor.submit(_fetch_pokemon_artwork, pokemon)
            for pokemon in ("pikachu", "garchomp")
        ]
        for request in as_completed(requests):
            try:
                pokemon, image = request.result()
            except RuntimeError as error:
                errors.append(str(error))
            else:
                artwork[pokemon] = image

    if not artwork:
        raise RuntimeError(" / ".join(errors))

    return artwork, errors
