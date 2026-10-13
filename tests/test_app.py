import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import app


class WebsiteTests(unittest.TestCase):
    def request(self, path, query="", method="GET"):
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        body = b"".join(
            app.application(
                {
                    "REQUEST_METHOD": method,
                    "PATH_INFO": path,
                    "QUERY_STRING": query,
                },
                start_response,
            )
        )
        return captured, body

    def test_all_pages_render_in_both_languages(self):
        for path in app.ROUTES:
            for lang, expected in (("de", 'lang="de"'), ("fr", 'lang="fr"')):
                with self.subTest(path=path, lang=lang):
                    response, body = self.request(path, f"lang={lang}")
                    self.assertEqual(response["status"], "200 OK")
                    self.assertIn(expected.encode(), body)
                    self.assertIn(b"/style.css", body)

    def test_old_php_url_redirects_and_keeps_query(self):
        response, _ = self.request("/aktuelles.php", "lang=fr")
        self.assertEqual(response["status"], "301 Moved Permanently")
        self.assertEqual(response["headers"]["Location"], "/aktuelles?lang=fr")

    def test_dynamic_content_is_escaped(self):
        article = app.Article("", "1", "1", "<script>", "A & B", None)
        rendered = app.article_card(article)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("A &amp; B", rendered)
        self.assertNotIn("<script>", rendered)

    def test_articles_are_sorted_by_year_and_number(self):
        articles = app.load_articles("historie")
        labels = [article.label for article in articles]
        self.assertEqual(labels, sorted(labels, reverse=True))

    def test_only_public_static_assets_are_served(self):
        css_response, css_body = self.request("/style.css")
        self.assertEqual(css_response["status"], "200 OK")
        self.assertIn(b".site-header", css_body)

        article_response, _ = self.request("/bilder/aktuelles/2026/01/artikel.txt")
        self.assertEqual(article_response["status"], "404 Not Found")

    def test_head_response_has_no_body(self):
        response, body = self.request("/", method="HEAD")
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(body, b"")
        self.assertGreater(int(response["headers"]["Content-Length"]), 0)


if __name__ == "__main__":
    unittest.main()
