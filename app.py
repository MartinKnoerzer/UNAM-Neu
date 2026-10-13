from __future__ import annotations

import argparse
import html
import mimetypes
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server


ROOT = Path(__file__).resolve().parent
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


@dataclass(frozen=True)
class Article:
    year: str
    number: str
    label: str
    title: str
    body: str
    image: str | None


@dataclass(frozen=True)
class Album:
    name: str
    images: tuple[tuple[str, str], ...]


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def tr(de: str, fr: str, lang: str) -> str:
    return fr if lang == "fr" else de


def page_url(page: str, lang: str) -> str:
    return f"{page}?lang={lang}"


def load_articles(archive_name: str, descending: bool = True) -> list[Article]:
    archive_root = ROOT / "bilder" / archive_name
    if not archive_root.exists():
        return []

    archive_directories = sorted(
        (entry for entry in archive_root.iterdir() if entry.is_dir()),
        key=lambda entry: entry.name,
        reverse=descending,
    )
    articles: list[Article] = []

    for archive_directory in archive_directories:
        directory_name = archive_directory.name
        if re.fullmatch(r"\d{4}", directory_name):
            year = directory_name
            article_directories = list(archive_directory.iterdir())
        elif re.fullmatch(r"\d+", directory_name):
            year = ""
            article_directories = [archive_directory]
        else:
            continue

        article_directories = [entry for entry in article_directories if entry.is_dir()]
        article_directories.sort(
            key=lambda entry: (int(entry.name) if entry.name.isdigit() else -1, entry.name),
            reverse=descending,
        )

        for article_directory in article_directories:
            article_number = article_directory.name
            if not re.fullmatch(r"\d+", article_number):
                continue

            files = sorted(entry for entry in article_directory.iterdir() if entry.is_file())
            article_file = next(
                (entry for entry in files if entry.name.lower() == "artikel.txt"),
                None,
            )
            image_file = next(
                (entry for entry in files if entry.suffix.lower() in IMAGE_EXTENSIONS),
                None,
            )
            if article_file is None:
                continue

            article_text = article_file.read_text(encoding="utf-8")
            article_text = article_text.replace("\r\n", "\n").replace("\r", "\n").strip()
            if not article_text:
                continue

            title, separator, body = article_text.partition("\n")
            title = title.strip()
            body = body.strip() if separator else ""
            image = image_file.relative_to(ROOT).as_posix() if image_file else None
            articles.append(
                Article(
                    year=year,
                    number=article_number,
                    label=f"{year} · {article_number}" if year else article_number,
                    title=title,
                    body=body,
                    image=image,
                )
            )

    return articles


def article_card(article: Article) -> str:
    body = f"<p>{escape(article.body).replace(chr(10), '<br>')}</p>" if article.body else ""
    image = ""
    if article.image:
        image = (
            f'<img src="{escape(article.image)}" alt="{escape(article.title)}" loading="lazy">'
        )
    label = f'<p class="eyebrow">{escape(article.label)}</p>'
    return (
        '<article class="news-article"><div class="news-article-copy">'
        f"{label}<h2>{escape(article.title)}</h2>{body}</div>{image}</article>"
    )


def header(lang: str, current_page: str) -> str:
    navigation = (
        ("/", "Startseite", "Accueil"),
        ("/about", "Über uns", "À propos"),
        ("/aktuelles", "Aktuelles", "Actualités"),
        ("/historie", "Historie", "Histoire"),
        ("/galerie", "Bildergalerie", "Galerie photos"),
    )
    links = []
    for url, de, fr in navigation:
        current = ' aria-current="page"' if url == current_page else ""
        links.append(
            f'<li><a href="{page_url(url, lang)}"{current}>'
            f"{escape(tr(de, fr, lang))}</a></li>"
        )

    open_label = tr("Menü öffnen", "Ouvrir le menu", lang)
    close_label = tr("Menü schließen", "Fermer le menu", lang)
    menu_label = tr("Hauptnavigation", "Navigation principale", lang)
    language_label = tr("Sprache wählen", "Choisir la langue", lang)
    brand_label = tr("Einheit und Freundschaft", "Unité et Amitié", lang)
    de_current = ' aria-current="true"' if lang == "de" else ""
    fr_current = ' aria-current="true"' if lang == "fr" else ""

    return f"""
<header class="site-header">
    <div class="container header-container">
        <a class="brand" href="{page_url('/', lang)}" aria-label="UNAM — Unité et Amitié">
            <span class="brand-mark" aria-hidden="true">U</span>
            <span class="brand-copy">
                <strong>UNAM</strong>
                <span>Unité et Amitié</span>
                <span>{escape(brand_label)}</span>
            </span>
        </a>
        <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="main-menu"
                data-open-label="{escape(open_label)}" data-close-label="{escape(close_label)}">
            <span class="sr-only">{escape(open_label)}</span>
            <span aria-hidden="true" class="menu-icon"></span>
        </button>
        <nav class="site-nav" aria-label="{escape(menu_label)}">
            <ul class="menu" id="main-menu">{''.join(links)}</ul>
        </nav>
        <div class="language-switch" aria-label="{escape(language_label)}">
            <a href="{page_url(current_page, 'de')}" lang="de"{de_current}>DE</a>
            <span aria-hidden="true">/</span>
            <a href="{page_url(current_page, 'fr')}" lang="fr"{fr_current}>FR</a>
        </div>
    </div>
</header>
<script>
    (function () {{
        var button = document.querySelector('.menu-toggle');
        var menu = document.getElementById('main-menu');
        if (!button || !menu) return;
        button.addEventListener('click', function () {{
            var isOpen = button.getAttribute('aria-expanded') === 'true';
            button.setAttribute('aria-expanded', String(!isOpen));
            menu.classList.toggle('is-open', !isOpen);
            button.closest('.header-container').querySelector('.site-nav').classList.toggle('is-open', !isOpen);
            button.querySelector('.sr-only').textContent = isOpen
                ? button.getAttribute('data-open-label')
                : button.getAttribute('data-close-label');
        }});
    }}());
</script>"""


def footer(lang: str) -> str:
    return f"""
<footer>
    <div class="container footer-container">
        <div class="footer-section">
            <a class="footer-brand" href="{page_url('/', lang)}">UNAM</a>
            <p>Unité et Amitié<br>{escape(tr('Einheit und Freundschaft', 'Unité et Amitié', lang))}</p>
        </div>
        <div class="footer-section footer-legal">
            <h2>{escape(tr('Rechtliches', 'Informations légales', lang))}</h2>
            <a href="{page_url('/impressum', lang)}">{escape(tr('Impressum', 'Mentions légales', lang))}</a>
            <a href="{page_url('/datenschutz', lang)}">{escape(tr('Datenschutz', 'Confidentialité', lang))}</a>
        </div>
    </div>
    <div class="footer-bottom"><p>© {date.today().year} UNAM</p></div>
</footer>"""


def document(
    lang: str,
    current_page: str,
    title: str,
    content: str,
    description: str = "",
    brand_first: bool = False,
) -> str:
    description_tag = f'<meta name="description" content="{escape(description)}">' if description else ""
    document_title = f"UNAM — {title}" if brand_first else f"{title} — UNAM"
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {description_tag}
    <title>{escape(document_title)}</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    {header(lang, current_page)}
    {content}
    {footer(lang)}
</body>
</html>"""


def home_page(lang: str) -> str:
    content = f"""
<main>
    <section class="hero">
        <div class="hero-image" role="img" aria-label="{escape(tr('Einblick in das UNAM-Haus', 'Aperçu de la maison UNAM', lang))}"></div>
        <div class="hero-shade"></div>
        <div class="container hero-content">
            <p class="eyebrow">{escape(tr('Einheit · Freundschaft · Gemeinschaft', 'Unité · Amitié · Communauté', lang))}</p>
            <h1>{escape(tr('Willkommen bei UNAM', 'Bienvenue chez UNAM', lang))}</h1>
            <p class="hero-lead">{escape(tr('Gemeinsam im Alltag, in Erinnerung und in der Zukunft.', 'Ensemble dans la vie quotidienne, dans le souvenir et dans l’avenir.', lang))}</p>
            <a class="button button-light" href="{page_url('/about', lang)}">{escape(tr('Mehr erfahren', 'En savoir plus', lang))}<span aria-hidden="true"> →</span></a>
        </div>
        <span class="hero-caption">{escape(tr('Gemeinsam verbunden', 'Unis par l’amitié', lang))}</span>
    </section>
    <section class="intro-section container">
        <div class="section-heading">
            <p class="eyebrow">{escape(tr('Schön, dass Sie da sind', 'Bienvenue', lang))}</p>
            <h2>{escape(tr('Ein Ort für Begegnung und Zusammenhalt', 'Un lieu de rencontre et de convivialité', lang))}</h2>
        </div>
        <div class="intro-copy">
            <p>{escape(tr('UNAM steht für Unité et Amitié – auf Deutsch: Einheit und Freundschaft. Diese Website stellt den Verein vor und bündelt Neuigkeiten, Erinnerungen und Bilder.', 'UNAM signifie Unité et Amitié. Ce site présente l’association et rassemble ses actualités, son histoire et ses photos.', lang))}</p>
            <p>{escape(tr('Die Inhalte wachsen mit dem gemeinsamen Vereinsleben – auf Deutsch und auf Französisch.', 'Le contenu évolue au rythme de la vie de l’association – en allemand et en français.', lang))}</p>
        </div>
    </section>
    <section class="explore-section">
        <div class="container">
            <div class="section-heading section-heading-row">
                <div>
                    <p class="eyebrow">{escape(tr('UNAM entdecken', 'Découvrir UNAM', lang))}</p>
                    <h2>{escape(tr('Was uns verbindet', 'Ce qui nous rassemble', lang))}</h2>
                </div>
                <p>{escape(tr('Einblicke in das Vereinsleben – Schritt für Schritt ergänzt.', 'Un aperçu de la vie de l’association, enrichi au fil du temps.', lang))}</p>
            </div>
            <div class="feature-grid">
                {feature_card('01', '/about', 'Über uns', 'À propos', 'Das Herz hinter UNAM.', 'Le cœur de UNAM.', lang)}
                {feature_card('02', '/aktuelles', 'Aktuelles', 'Actualités', 'Neuigkeiten, Termine und gemeinsame Aktivitäten.', 'Nouvelles, rendez-vous et activités communes.', lang)}
                {feature_card('03', '/historie', 'Historie', 'Histoire', 'Erinnerungen und Ereignisse nach Jahren.', 'Souvenirs et événements classés par année.', lang)}
                {feature_card('04', '/galerie', 'Bildergalerie', 'Galerie photos', 'Gemeinsame Momente in Bildern.', 'Des moments partagés en images.', lang)}
            </div>
        </div>
    </section>
</main>"""
    return document(
        lang,
        "/",
        tr("Einheit und Freundschaft", "Unité et Amitié", lang),
        content,
        tr(
            "UNAM – Unité et Amitié: Einheit und Freundschaft. Informationen über den Verein, aktuelle Aktivitäten, Geschichte und Bilder.",
            "UNAM – Unité et Amitié : informations sur l’association, ses actualités, son histoire et ses photos.",
            lang,
        ),
        brand_first=True,
    )


def feature_card(
    number: str,
    url: str,
    title_de: str,
    title_fr: str,
    description_de: str,
    description_fr: str,
    lang: str,
) -> str:
    return (
        f'<a class="feature-card" href="{page_url(url, lang)}">'
        f'<span class="card-number">{number}</span>'
        f"<h3>{escape(tr(title_de, title_fr, lang))}</h3>"
        f"<p>{escape(tr(description_de, description_fr, lang))}</p>"
        '<span class="card-arrow" aria-hidden="true">↗</span></a>'
    )


def page_hero(eyebrow: str, title: str, lead: str, lang: str) -> str:
    lead_html = f"<p class=\"page-lead\">{escape(lead)}</p>" if lead else ""
    return (
        '<section class="page-hero container">'
        f'<p class="eyebrow">{escape(eyebrow)}</p><h1>{escape(title)}</h1>{lead_html}'
        "</section>"
    )


def news_page(
    lang: str,
    page: str,
    title_de: str,
    title_fr: str,
    eyebrow_de: str,
    eyebrow_fr: str,
    lead_de: str,
    lead_fr: str,
    archive: str,
    empty_de: str,
    empty_fr: str,
    section_de: str,
    section_fr: str,
) -> str:
    title = tr(title_de, title_fr, lang)
    articles = load_articles(archive)
    content = page_hero(
        tr(eyebrow_de, eyebrow_fr, lang),
        title,
        tr(lead_de, lead_fr, lang),
        lang,
    )
    if articles:
        content += (
            f'<section class="container news-articles" aria-label="{escape(tr(section_de, section_fr, lang))}">'
            + "".join(article_card(article) for article in articles)
            + "</section>"
        )
    else:
        content += (
            f'<p class="content-note container">{escape(tr(empty_de, empty_fr, lang))}</p>'
        )
    return document(lang, page, title, f'<main class="page-main">{content}</main>')


def about_page(lang: str) -> str:
    articles = load_articles("uberuns", descending=False)
    content = page_hero(
        tr("Lernen Sie uns kennen", "Faisons connaissance", lang),
        tr("Über uns", "À propos", lang),
        tr(
            "Unité et Amitié – Einheit und Freundschaft. Zwei Sprachen, ein gemeinsamer Gedanke.",
            "Unité et Amitié – unité et amitié. Deux langues, une idée commune.",
            lang,
        ),
        lang,
    )
    content += f"""
<section class="about-layout container">
    <div class="about-photo"><img src="/bilder/startseite/unam-002.jpg" alt="{escape(tr('Das UNAM-Haus', 'La maison UNAM', lang))}"></div>
    <div class="about-copy">
        <p class="eyebrow">{escape(tr('Unser Name', 'Notre nom', lang))}</p>
        <h2>Unité et Amitié</h2>
        <p>{escape(tr('Der Name UNAM bedeutet „Einheit und Freundschaft“. Er bringt den Gedanken zum Ausdruck, der den Verein prägt: Menschen zusammenzubringen und Gemeinschaft zu pflegen.', 'Le nom UNAM signifie « unité et amitié ». Il exprime l’idée qui anime l’association : rassembler les personnes et cultiver les liens entre elles.', lang))}</p>
        <p>{escape(tr('Auf dieser Website finden Sie Informationen über den Verein, aktuelle Aktivitäten, Ereignisse aus der Geschichte und Bilder gemeinsamer Momente. Die Inhalte werden nach und nach ergänzt.', 'Ce site vous propose des informations sur l’association, ses activités, des événements de son histoire et des photos de moments partagés. Son contenu sera complété progressivement.', lang))}</p>
    </div>
</section>"""
    if articles:
        values = []
        for article in articles:
            anchor = f"about-article-{article.number}"
            excerpt = f"<p>{escape(article.body.splitlines()[0])}</p>" if article.body else ""
            values.append(
                f'<a class="about-value-link" href="#{escape(anchor)}">'
                f"<h2>{escape(article.title)}</h2>{excerpt}</a>"
            )
        content += (
            '<section class="values-band"><nav class="container values-grid" '
            f'aria-label="{escape(tr("Themen in Über uns", "Rubriques À propos", lang))}">'
            + "".join(values)
            + "</nav></section>"
        )
        content += (
            f'<section class="container news-articles about-articles" aria-label="{escape(tr("Artikel über uns", "Articles à propos de nous", lang))}">'
            + "".join(
                article_card_with_anchor(article, f"about-article-{article.number}")
                for article in articles
            )
            + "</section>"
        )
    else:
        values = (
            ("Einheit", "Unité", "Zusammenkommen und Gemeinschaft erleben.", "Se retrouver et partager des moments ensemble."),
            ("Freundschaft", "Amitié", "Begegnungen und Verbundenheit pflegen.", "Faire vivre les rencontres et les liens d’amitié."),
            ("Austausch", "Échange", "Informationen und Erinnerungen zweisprachig teilen.", "Partager actualités et souvenirs dans les deux langues."),
        )
        cards = "".join(
            f"<div><h2>{escape(tr(de, fr, lang))}</h2><p>{escape(tr(body_de, body_fr, lang))}</p></div>"
            for de, fr, body_de, body_fr in values
        )
        content += f'<section class="values-band"><div class="container values-grid">{cards}</div></section>'
    return document(lang, "/about", tr("Über uns", "À propos", lang), f'<main class="page-main">{content}</main>')


def article_card_with_anchor(article: Article, anchor: str) -> str:
    card = article_card(article)
    return card.replace('<article class="news-article">', f'<article class="news-article" id="{escape(anchor)}">', 1)


def gallery_page(lang: str) -> str:
    intro_images = (
        ("bilder/startseite/unam-001.jpg", tr("Einblick in die UNAM-Anlage", "Aperçu du domaine UNAM", lang)),
        ("bilder/startseite/unam-002.jpg", tr("Das UNAM-Haus", "La maison UNAM", lang)),
    )
    grid = "".join(
        f'<figure class="photo-card"><img src="/{escape(src)}" alt="{escape(alt)}" loading="lazy">'
        f'<figcaption>{escape(tr("Einblicke in UNAM", "Aperçus d’UNAM", lang))}</figcaption></figure>'
        for src, alt in intro_images
    )

    gallery_root = ROOT / "bilder" / "bildergalerie"
    archive_html = []
    if gallery_root.is_dir():
        year_directories = sorted(
            (entry for entry in gallery_root.iterdir() if entry.is_dir()),
            key=lambda entry: entry.name,
        )
        for year_directory in year_directories:
            year = year_directory.name
            if not re.fullmatch(r"\d{4}", year):
                continue
            albums = []
            album_directories = sorted(
                (entry for entry in year_directory.iterdir() if entry.is_dir()),
                key=lambda entry: entry.name,
            )
            for album_directory in album_directories:
                album_name = album_directory.name
                image_files = sorted(
                    (
                        entry
                        for entry in album_directory.iterdir()
                        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS
                    ),
                    key=lambda entry: entry.name,
                )
                images = tuple(
                    (
                        image.relative_to(ROOT).as_posix(),
                        tr(
                            f"Foto aus {album_name}, {year}",
                            f"Photo de {album_name}, {year}",
                            lang,
                        ),
                    )
                    for image in image_files
                )
                if images:
                    albums.append(Album(album_name, images))
            if albums:
                album_html = []
                for album in albums:
                    album_grid = "".join(
                        f'<figure class="photo-card"><img src="/{escape(src)}" alt="{escape(alt)}" loading="lazy">'
                        f'<figcaption>{escape(album.name)} · {escape(year)}</figcaption></figure>'
                        for src, alt in album.images
                    )
                    album_html.append(
                        f"<div class=\"archive-album\"><h3>{escape(album.name)}</h3>"
                        f'<div class="photo-grid">{album_grid}</div></div>'
                    )
                archive_html.append(
                    f'<section class="archive-year"><h2>{escape(year)}</h2>{"".join(album_html)}</section>'
                )

    content = page_hero(
        tr("Gemeinsame Momente", "Des moments partagés", lang),
        tr("Bildergalerie", "Galerie photos", lang),
        tr(
            "Einblicke in Bilder – später nach Jahren und Anlässen sortiert.",
            "Des moments en images – à classer par année et par occasion.",
            lang,
        ),
        lang,
    )
    content += f"""
<section class="container gallery-section">
    <div class="gallery-heading">
        <h2>{escape(tr('Einblicke', 'Aperçus', lang))}</h2>
        <p>{escape(tr('Weitere Galerien können nach Jahr und Anlass ergänzt werden – zum Beispiel Pfingsten, Herbst oder Sommer. Lege dazu einen Jahresordner und darin einen Ordner pro Anlass unter bilder/bildergalerie an.', 'D’autres galeries peuvent être ajoutées par année et par occasion – par exemple Pentecôte, automne ou été. Pour cela, créez un dossier par année, puis un dossier par occasion dans bilder/bildergalerie.', lang))}</p>
    </div>
    <div class="photo-grid">{grid}</div>
    {''.join(archive_html)}
</section>"""
    return document(lang, "/galerie", tr("Bildergalerie", "Galerie photos", lang), f'<main class="page-main">{content}</main>')


LEGAL_DEFAULTS = {
    "association_name": "UNAM – Unité et Amitié",
    "legal_name": "UNAM – Unité et Amitié",
    "representative": "Didier Arnoud / Didier Arnoud",
    "street": "21120 Crécey-sur-Tille",
    "city": "21120 Crécey-sur-Tille",
    "country": "France",
    "contact_email": "didier.arnoud67@orange.fr",
    "website": "https://www.unam-website.fr",
    "responsible_name": "Didier Arnoud",
    "responsible_address": "21120 Crécey-sur-Tille",
    "hosting_provider": "Hosting-Anbieter / Hébergeur",
    "hosting_details": "Daten werden gemäß Hosting-Vertrag und Datenschutzanforderungen verarbeitet / Les données sont traitées conformément au contrat d’hébergement et aux exigences de protection des données",
}

LEGAL_COPY = {
    "impressum": {
        "title": ("Impressum", "Mentions légales"),
        "eyebrow": ("Rechtliche Angaben", "Informations légales"),
        "notice": (
            "Die folgenden Angaben sind ein realistisches Beispiel für die Website-Vorbereitung. Bitte prüfen Sie vor dem Launch die Daten noch mit den offiziellen Vereinsangaben ab.",
            "Les informations ci-dessous sont un exemple réaliste pour la préparation du site. Avant le lancement, veuillez encore vérifier ces données avec les coordonnées officielles de l’association.",
        ),
        "sections": (
            (("Angaben gemäß § 5 DDG", "Informations conformément au § 5 DDG"),
             (f"{LEGAL_DEFAULTS['legal_name']}\n{LEGAL_DEFAULTS['representative']}\n{LEGAL_DEFAULTS['street']}\n{LEGAL_DEFAULTS['city']}\n{LEGAL_DEFAULTS['country']}\n{LEGAL_DEFAULTS['website']}",
              f"{LEGAL_DEFAULTS['legal_name']}\n{LEGAL_DEFAULTS['representative']}\n{LEGAL_DEFAULTS['street']}\n{LEGAL_DEFAULTS['city']}\n{LEGAL_DEFAULTS['country']}\n{LEGAL_DEFAULTS['website']}")),
            (("Kontakt", "Contact"),
             (f"E-Mail: {LEGAL_DEFAULTS['contact_email']}\nWebsite: {LEGAL_DEFAULTS['website']}",
              f"E-mail : {LEGAL_DEFAULTS['contact_email']}\nSite web : {LEGAL_DEFAULTS['website']}")),
            (("Verantwortlich für den Inhalt", "Responsable du contenu"),
             (f"{LEGAL_DEFAULTS['responsible_name']}\n{LEGAL_DEFAULTS['responsible_address']}",
              f"{LEGAL_DEFAULTS['responsible_name']}\n{LEGAL_DEFAULTS['responsible_address']}")),
            (("Haftung für Inhalte", "Responsabilité relative aux contenus"),
             ("Die Inhalte dieser Website werden mit Sorgfalt erstellt. Für Richtigkeit, Vollständigkeit und Aktualität kann jedoch keine Gewähr übernommen werden.",
              "Les contenus de ce site sont préparés avec soin. Aucune garantie ne peut toutefois être donnée quant à leur exactitude, leur exhaustivité ou leur actualité.")),
            (("Urheberrecht", "Droit d’auteur"),
             ("Die Inhalte und Werke auf dieser Website unterliegen dem jeweils geltenden Urheberrecht. Eine Verwendung außerhalb der gesetzlichen Grenzen bedarf der vorherigen Zustimmung der jeweiligen Rechteinhaber.",
              "Les contenus et œuvres de ce site sont soumis au droit d’auteur applicable. Toute utilisation en dehors des limites prévues par la loi nécessite l’accord préalable des titulaires des droits.")),
        ),
    },
    "datenschutz": {
        "title": ("Datenschutz", "Confidentialité"),
        "heading": ("Datenschutzhinweise", "Protection des données"),
        "eyebrow": ("Ihre Daten", "Vos données"),
        "lead": (
            "Informationen zur Verarbeitung personenbezogener Daten beim Besuch dieser Website.",
            "Informations sur le traitement des données personnelles lors de la visite de ce site.",
        ),
        "notice": (
            "Diese Hinweise sind als vollständige, praxisnahe Vorlage für den Start vorbereitet. Vor dem Live-Start sind die Angaben zur verantwortlichen Stelle, zu Kontaktdaten und zum Hosting-Anbieter mit den tatsächlichen Betriebsdaten abzugleichen.",
            "Ces informations sont préparées comme modèle complet et pratique pour le lancement. Avant le lancement, les coordonnées du responsable du traitement, les informations de contact et les données de l’hébergeur doivent être vérifiées et adaptées au fonctionnement réel du site.",
        ),
        "sections": (
            (("Verantwortliche Stelle", "Responsable du traitement"),
             (f"{LEGAL_DEFAULTS['association_name']}\n{LEGAL_DEFAULTS['legal_name']}\n{LEGAL_DEFAULTS['contact_email']}\n{LEGAL_DEFAULTS['responsible_address']}\n{LEGAL_DEFAULTS['website']}",
              f"{LEGAL_DEFAULTS['association_name']}\n{LEGAL_DEFAULTS['legal_name']}\n{LEGAL_DEFAULTS['contact_email']}\n{LEGAL_DEFAULTS['responsible_address']}\n{LEGAL_DEFAULTS['website']}")),
            (("Aufruf der Website", "Consultation du site"),
             (f"Beim Aufruf der Website können technische Zugriffsdaten durch {LEGAL_DEFAULTS['hosting_provider']} in Server-Log-Dateien verarbeitet werden. Die genauen Speicherfristen und die Rechtsgrundlage sind gemäß Hosting-Vertrag und geltender Datenschutzanforderungen zu prüfen.",
              f"Lors de la consultation du site, des données techniques d’accès peuvent être traitées par {LEGAL_DEFAULTS['hosting_provider']} dans des fichiers journaux. Les durées de conservation exactes et la base juridique doivent être vérifiées conformément au contrat d’hébergement et aux exigences applicables en matière de protection des données.")),
            (("Cookies und externe Dienste", "Cookies et services externes"),
             ("Bitte prüfen und dokumentieren Sie, ob der tatsächliche Betrieb Cookies, eingebettete Inhalte, Analysewerkzeuge oder weitere externe Dienste verwendet. Diese Vorlage setzt nicht voraus, dass solche Dienste eingesetzt werden.",
              "Veuillez vérifier et documenter si le site utilise réellement des cookies, des contenus intégrés, des outils d’analyse ou d’autres services externes. Ce modèle ne présume pas de l’utilisation de tels services.")),
            (("Ihre Rechte", "Vos droits"),
             ("Betroffene Personen haben im Rahmen der geltenden Datenschutzgesetze Rechte, etwa auf Auskunft, Berichtigung, Löschung und Einschränkung der Verarbeitung. Für Fragen zum Datenschutz wenden Sie sich bitte an die verantwortliche Stelle. Sie können sich außerdem bei einer zuständigen Datenschutzaufsichtsbehörde beschweren.",
              "Les personnes concernées disposent, dans le cadre des lois applicables en matière de protection des données, de droits tels que l’accès, la rectification, l’effacement et la limitation du traitement. Pour toute question, veuillez contacter le responsable du traitement. Vous pouvez également déposer une réclamation auprès d’une autorité de contrôle compétente.")),
        ),
    },
}


def legal_page(kind: str, lang: str) -> str:
    copy = LEGAL_COPY[kind]
    title = tr(*copy["title"], lang)
    if kind == "datenschutz":
        heading = tr(*copy["heading"], lang)
        lead = tr(*copy["lead"], lang)
    else:
        heading = title
        lead = ""

    content = page_hero(tr(*copy["eyebrow"], lang), heading, lead, lang)
    content += f'<section class="container legal-content"><p class="legal-notice">{escape(tr(*copy["notice"], lang))}</p>'
    for section_heading, section_body in copy["sections"]:
        paragraph = escape(tr(*section_body, lang)).replace("\n", "<br>\n")
        content += f"<h2>{escape(tr(*section_heading, lang))}</h2><p>{paragraph}</p>"
    content += "</section>"
    route = f"/{kind}"
    return document(lang, route, title, f'<main class="page-main">{content}</main>')


ROUTES: dict[str, Callable[[str], str]] = {
    "/": home_page,
    "/about": about_page,
    "/aktuelles": lambda lang: news_page(
        lang,
        "/aktuelles",
        "Aktuelles",
        "Actualités",
        "Aus dem Vereinsleben",
        "La vie de l’association",
        "Neuigkeiten, Termine und Einblicke in gemeinsame Aktivitäten.",
        "Nouvelles, rendez-vous et aperçu des activités communes.",
        "aktuelles",
        "Neue Meldungen erscheinen hier, sobald aktuelle Informationen vorliegen.",
        "Les nouvelles seront publiées ici dès que des informations seront disponibles.",
        "Aktuelle Artikel",
        "Articles récents",
    ),
    "/historie": lambda lang: news_page(
        lang,
        "/historie",
        "Historie",
        "Histoire",
        "Erinnerungen bewahren",
        "Faire vivre les souvenirs",
        "Jahr für Jahr – Ereignisse, Begegnungen und gemeinsame Erinnerungen.",
        "Année après année – événements, rencontres et souvenirs partagés.",
        "historie",
        "Jahresübersichten und Ereignisse werden hier veröffentlicht, sobald die Informationen vorliegen.",
        "Les rétrospectives annuelles et les événements seront publiés ici dès que les informations seront disponibles.",
        "Chronik-Artikel",
        "Articles de la chronique",
    ),
    "/galerie": gallery_page,
    "/impressum": lambda lang: legal_page("impressum", lang),
    "/datenschutz": lambda lang: legal_page("datenschutz", lang),
}

PHP_REDIRECTS = {
    "/index.php": "/",
    "/about.php": "/about",
    "/aktuelles.php": "/aktuelles",
    "/historie.php": "/historie",
    "/galerie.php": "/galerie",
    "/impressum.php": "/impressum",
    "/datenschutz.php": "/datenschutz",
}


def response(
    start_response,
    status: str,
    body: bytes,
    content_type: str,
    headers=(),
    content_length: int | None = None,
):
    response_headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body) if content_length is None else content_length)),
        ("X-Content-Type-Options", "nosniff"),
    ]
    response_headers.extend(headers)
    start_response(status, response_headers)
    return [body]


def serve_static(path: str, method: str, start_response):
    if path == "/style.css":
        requested = ROOT / "style.css"
    elif path.startswith("/bilder/"):
        requested = ROOT / path.lstrip("/")
    else:
        return None

    try:
        resolved = requested.resolve(strict=True)
        resolved.relative_to(ROOT)
    except FileNotFoundError:
        return response(start_response, "404 Not Found", b"Not found", "text/plain; charset=utf-8")
    except ValueError:
        return response(start_response, "404 Not Found", b"Not found", "text/plain; charset=utf-8")

    if not resolved.is_file() or (
        resolved.suffix.lower() not in IMAGE_EXTENSIONS and resolved.name != "style.css"
    ):
        return response(start_response, "404 Not Found", b"Not found", "text/plain; charset=utf-8")

    content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    if content_type.startswith("text/"):
        content_type += "; charset=utf-8"
    body = resolved.read_bytes()
    if method == "HEAD":
        return response(
            start_response,
            "200 OK",
            b"",
            content_type,
            content_length=len(body),
        )
    return response(start_response, "200 OK", body, content_type)


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    if method not in {"GET", "HEAD"}:
        return response(
            start_response,
            "405 Method Not Allowed",
            b"Method not allowed",
            "text/plain; charset=utf-8",
            [("Allow", "GET, HEAD")],
        )

    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    if path in PHP_REDIRECTS:
        location = PHP_REDIRECTS[path]
        if query:
            location += "?" + query
        return response(
            start_response,
            "301 Moved Permanently",
            b"",
            "text/plain; charset=utf-8",
            [("Location", location)],
        )

    static_response = serve_static(path, method, start_response)
    if static_response is not None:
        return static_response

    renderer = ROUTES.get(path)
    if renderer is None:
        page = document(
            "de",
            "",
            "Seite nicht gefunden",
            '<main class="page-main"><section class="page-hero container">'
            '<h1>Seite nicht gefunden</h1><p class="page-lead">Die angeforderte Seite existiert nicht.</p>'
            "</section></main>",
        ).encode("utf-8")
        return response(start_response, "404 Not Found", page, "text/html; charset=utf-8")

    query_values = parse_qs(query, keep_blank_values=True)
    lang = "fr" if query_values.get("lang", ["de"])[0] == "fr" else "de"
    body = renderer(lang).encode("utf-8")
    if method == "HEAD":
        return response(
            start_response,
            "200 OK",
            b"",
            "text/html; charset=utf-8",
            content_length=len(body),
        )
    return response(start_response, "200 OK", body, "text/html; charset=utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the UNAM website using Python.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    with make_server(args.host, args.port, application) as server:
        print(f"UNAM website available at http://{args.host}:{args.port}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
