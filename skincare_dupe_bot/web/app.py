from flask import Flask, redirect, render_template, request, send_from_directory, url_for

from skincare_dupe_bot import config
from skincare_dupe_bot.database.db import get_session, init_db
from skincare_dupe_bot.database.models import DrugstoreDupe, GeneratedVideo, KBeautyProduct
from skincare_dupe_bot.scrapers.price_tracker import check_one_dupe
from skincare_dupe_bot.video.generator import generate_reel

app = Flask(__name__)


@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    with get_session() as session:
        kbeauty_products = session.query(KBeautyProduct).order_by(KBeautyProduct.brand).all()
        if q:
            kbeauty_products = [
                kb for kb in kbeauty_products
                if q in kb.brand.lower() or q in kb.name.lower()
                or any(q in d.brand.lower() or q in d.name.lower() for d in kb.dupes)
            ]
        # Rendered inside the session block: templates walk kb.dupes, a
        # lazy relationship that can't load once the session is closed.
        return render_template("index.html", kbeauty_products=kbeauty_products, q=q)


@app.route("/dupe/<int:dupe_id>")
def dupe_detail(dupe_id):
    with get_session() as session:
        dupe = session.get(DrugstoreDupe, dupe_id)
        if dupe is None:
            return "Not found", 404
        history = sorted(dupe.price_history, key=lambda h: h.checked_at, reverse=True)[:20]
        dupe_videos = sorted(dupe.videos, key=lambda v: v.created_at, reverse=True)
        return render_template("dupe_detail.html", dupe=dupe, history=history, videos=dupe_videos)


@app.route("/videos")
def videos():
    with get_session() as session:
        all_videos = session.query(GeneratedVideo).order_by(GeneratedVideo.created_at.desc()).all()
        return render_template("videos.html", videos=all_videos)


@app.route("/media/<path:filename>")
def media(filename):
    return send_from_directory(config.VIDEO_OUTPUT_DIR, filename)


@app.route("/dupe/<int:dupe_id>/check_price", methods=["POST"])
def trigger_price_check(dupe_id):
    with get_session() as session:
        dupe = session.get(DrugstoreDupe, dupe_id)
        if dupe is None:
            return "Not found", 404
        result = check_one_dupe(dupe)
        if result.price_usd is not None:
            dupe.last_known_price_usd = result.price_usd
            dupe.product_url = result.product_url
    return redirect(url_for("dupe_detail", dupe_id=dupe_id))


@app.route("/dupe/<int:dupe_id>/generate_video", methods=["POST"])
def trigger_video(dupe_id):
    with get_session() as session:
        dupe = session.get(DrugstoreDupe, dupe_id)
        if dupe is None:
            return "Not found", 404
        kb = dupe.kbeauty_product
        generate_reel(kb, dupe, trigger_reason="manual")
    return redirect(url_for("dupe_detail", dupe_id=dupe_id))


def main():
    init_db()
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False)


if __name__ == "__main__":
    main()
