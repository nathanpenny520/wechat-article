#!/usr/bin/env python3
"""Heuristic style-risk checks for WeWrite articles.

The command catches mechanical issues such as repetitive sentence shapes,
cliches, excessive adverbs, fragments, and weak source attribution. It does
not determine whether a text is human-written and it cannot verify facts.

Usage:
    wewrite score article.md                    # single score
    wewrite score article.md --verbose          # detailed report
    wewrite score article.md --json             # full JSON
    wewrite score article.md --json --tier3 0.7 # with agent score
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ============================================================
# Constants
# ============================================================

BANNED_WORDS = [
    "首先", "其次", "再者", "最后", "总之", "综上所述", "总而言之",
    "此外", "另外", "与此同时", "不仅如此", "更重要的是", "在此基础上",
    "作为一个", "让我们", "值得注意的是", "需要指出的是", "不可否认",
    "毋庸置疑", "众所周知", "事实上", "显而易见", "可以说", "从某种意义上说",
    "非常重要", "至关重要", "不言而喻", "具有重要意义", "发挥着重要作用",
    "意义深远", "影响深远", "引发了广泛关注", "引起了热烈讨论",
    "总的来说", "综合来看", "由此可见", "不难发现", "通过以上分析",
    "正如我们所看到的",
]

REAL_SOURCE_PATTERNS = [
    r'[A-Z][a-z]+\s+[A-Z][a-z]+',
    r'[\u4e00-\u9fff]{2,4}(?:表示|指出|认为|写道|提到|说过)',
    r'(?:据|根据|来自)\s*[\u4e00-\u9fff]+(?:报告|数据|研究|调查)',
    r'20[12]\d\s*年',
    r'\d+(?:\.\d+)?%',
    r'(?:亿|万)\s*(?:美元|元|人民币)',
]

NEGATIVE_MARKERS = [
    # 直接负面情绪
    "失望", "糟糕", "扯", "坑", "烂", "差劲", "崩溃", "吐槽", "骂",
    "怒", "烦", "焦虑", "担忧", "不满", "恶心", "可怕", "可悲", "可笑",
    "离谱", "尴尬", "无语", "蠢", "惨", "亏", "危",
    # 绝望/迷茫
    "绝望", "迷茫", "心累", "丧", "后悔", "后怕", "心寒",
    # 欺骗/操控（隐性负面）
    "骗", "忽悠", "割韭菜", "套路", "画大饼", "洗脑",
    # 失败/徒劳
    "白费", "白搭", "没戏", "黄了", "凉了", "废了",
    # 自嘲/自贬
    "傻", "天真", "吃亏", "自嗨", "打脸",
    # 讽刺/反语
    "呵呵", "好吧", "行吧", "真服了",
    # 短语
    "太扯了", "说实话我很失望", "搞什么", "不靠谱", "受不了",
    "受够了", "想哭", "伤心", "苦哈哈", "得过且过",
]

COMMON_ADVERBS = [
    "非常", "十分", "极其", "特别", "相当", "尤其", "格外",
    "更加", "越来越", "逐渐", "不断", "始终", "一直",
    "已经", "正在", "将要", "可能", "大概", "或许",
    "似乎", "显然", "明显", "确实", "果然", "居然",
    "竟然", "简直", "几乎", "完全", "绝对", "必然",
]

COLD_WORDS = [
    "边际", "认知负荷", "信息不对称", "路径依赖", "商业模式", "生态系统", "增量",
    "技术栈", "标准化", "结构性", "规模化", "护城河", "飞轮", "闭环",
    "赛道", "壁垒", "方法论", "底层逻辑", "第一性原理", "杠杆", "复利",
    "ROI", "PMF", "代运营", "供给侧", "需求侧",
]
WARM_WORDS = [
    "说白了", "其实吧", "讲真", "说实话", "坦白讲", "懂的都懂", "怎么说呢",
    "老实说", "这么说吧", "你想啊", "别急", "慢慢来",
    "有意思的是", "好玩的是", "巧的是", "说来话长", "话说回来",
]
HOT_WORDS = [
    "DNA动了", "格局打开", "遥遥领先", "卷", "内卷", "炸了", "杀疯了", "吃灰",
    "凡尔赛", "标题党", "躺平", "摆烂", "破防", "上头", "内耗",
    "蒸发", "出圈", "降维打击", "弯道超车",
]
WILD_WORDS = [
    "整挺好", "不靠谱", "瞎折腾", "搁这儿", "糊弄", "扯", "嗯",
    "苦哈哈", "傻乎乎", "稀里糊涂", "得了吧", "算了吧",
    "摔了跤", "交学费", "踩坑", "翻车", "栽了",
]

SELF_CORRECTION_PATTERNS = [
    r'不对[，,]', r'准确说', r'算了', r'说错了',
    r'其实不是', r'我记混了', r'应该说', r'更准确地说',
    r'（[^）]{4,}）',  # Chinese parenthetical insertion (≥4 chars)
]

BROKEN_SENTENCE_PATTERNS = [
    r'——(?!.*[，。！？])',
    r'\.{3,}|…',
    r'不对[，,]',
    r'算了',
]


# ============================================================
# Helpers
# ============================================================

def _split_sentences(text):
    """Split text by Chinese sentence-ending and clause-level punctuation."""
    sentences = re.split(r'[。！？；;…\n]', text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 1]


def _split_paragraphs(text):
    """Split text into paragraphs, excluding headings."""
    return [p.strip() for p in text.split('\n\n')
            if p.strip() and not p.strip().startswith('#')]


def _make_result(score, detail, param=None):
    """Create a check result dict."""
    r = {"score": round(max(0.0, min(1.0, score)), 4), "detail": detail}
    if param is not None:
        r["param"] = param
    else:
        r["param"] = None
    return r


# ============================================================
# Tier 1: Statistical Checks (weight 50%)
# ============================================================

def score_sentence_length_stddev(text):
    """[1.1] Sentence length standard deviation. → sentence_variance"""
    sentences = _split_sentences(text)
    if len(sentences) < 5:
        return _make_result(0.5, "too few sentences to measure", "sentence_variance")
    lengths = [len(s) for s in sentences]
    mean = sum(lengths) / len(lengths)
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    stddev = variance ** 0.5
    score = min(1.0, stddev / 25.0)
    return _make_result(score, f"stddev={stddev:.1f} (target ≥15)", "sentence_variance")


def score_sentence_length_range(text):
    """[1.1] Sentence length range (max - min). → sentence_variance"""
    sentences = _split_sentences(text)
    if len(sentences) < 5:
        return _make_result(0.5, "too few sentences", "sentence_variance")
    lengths = [len(s) for s in sentences]
    rng = max(lengths) - min(lengths)
    range_score = min(1.0, rng / 40.0)
    # Check for single-sentence short paragraphs
    lines = text.split('\n')
    short_paras = sum(1 for l in lines if l.strip() and 1 <= len(l.strip()) <= 5
                      and not l.strip().startswith('#'))
    expected = max(1, len(text) / 500)
    short_score = min(1.0, short_paras / expected)
    score = range_score * 0.6 + short_score * 0.4
    return _make_result(score, f"range={rng} (target ≥30), short_paras={short_paras}", "sentence_variance")


def score_paragraph_length_variance(text):
    """[1.3] Paragraph length variance. → paragraph_rhythm"""
    paragraphs = _split_paragraphs(text)
    if len(paragraphs) < 3:
        return _make_result(0.5, "too few paragraphs", "paragraph_rhythm")
    total_pairs = len(paragraphs) - 1
    similar = sum(1 for i in range(total_pairs)
                  if abs(len(paragraphs[i]) - len(paragraphs[i + 1])) <= 20)
    score = 1.0 - (similar / total_pairs) if total_pairs > 0 else 0.5
    return _make_result(score, f"{similar}/{total_pairs} consecutive similar-length pairs", "paragraph_rhythm")


def score_vocabulary_richness(text):
    """CJK bigram diversity without rewarding arbitrary slang mixtures."""
    cjk_chars = re.findall(r'[\u4e00-\u9fff]', text)
    if len(cjk_chars) < 20:
        return _make_result(0.5, "too few CJK characters", "word_temperature_bias")
    bigrams = [cjk_chars[i] + cjk_chars[i + 1] for i in range(len(cjk_chars) - 1)]
    ttr = len(set(bigrams)) / len(bigrams) if bigrams else 0
    ttr_score = min(1.0, ttr / 0.7)
    return _make_result(ttr_score, f"bigram_ttr={ttr:.3f}", "vocabulary_diversity")


def score_emotional_balance(text):
    """Do not require negativity; only flag an article dominated by it."""
    sentences = _split_sentences(text)
    if not sentences:
        return _make_result(0.5, "no sentences", "emotional_arc")
    negative_count = sum(1 for s in sentences
                         if any(m in s for m in NEGATIVE_MARKERS))
    ratio = negative_count / len(sentences)
    score = 1.0 if ratio <= 0.35 else max(0.0, 1.0 - (ratio - 0.35) * 2)
    return _make_result(score, f"negative markers={negative_count}/{len(sentences)} ({ratio:.0%})", "emotional_balance")


def score_adverb_density(text):
    """[1.5] Adverb density control. → adverb_max_per_100"""
    char_count = len(text)
    if char_count < 50:
        return _make_result(0.5, "text too short", "adverb_max_per_100")
    # Count adverb occurrences
    total_adverbs = sum(text.count(adv) for adv in COMMON_ADVERBS)
    density = total_adverbs / char_count * 100
    # Check consecutive sentences starting with adverbs
    sentences = _split_sentences(text)
    consecutive_adverb_starts = 0
    for i in range(len(sentences) - 1):
        a_starts = any(sentences[i].startswith(adv) for adv in COMMON_ADVERBS)
        b_starts = any(sentences[i + 1].startswith(adv) for adv in COMMON_ADVERBS)
        if a_starts and b_starts:
            consecutive_adverb_starts += 1
    score = 1.0
    if density > 3.0:
        score -= min(0.5, (density - 3.0) * 0.1)
    score -= consecutive_adverb_starts * 0.3
    return _make_result(score, f"density={density:.1f}/100chars, consecutive_starts={consecutive_adverb_starts}", "adverb_max_per_100")


# ============================================================
# Tier 2: Pattern Checks (weight 30%)
# ============================================================

def score_banned_words(text):
    """[2.1] Banned word check. → null (hard rule, no config param)"""
    found = [w for w in BANNED_WORDS if w in text]
    score = max(0.0, 1.0 - len(found) * 0.2)
    detail = "0 banned words" if not found else f"{len(found)} found: {found[:5]}"
    return _make_result(score, detail, None)


def score_sentence_integrity(text):
    """Penalize excessive fragments instead of requiring them."""
    count = 0
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for p in BROKEN_SENTENCE_PATTERNS:
            count += len(re.findall(p, line))
        if 1 <= len(line) <= 10 and not line.startswith('#'):
            count += 1
    char_count = len(text)
    allowed = max(1, char_count / 1000)
    score = max(0.0, 1.0 - max(0, count - allowed) / max(3, allowed * 3))
    return _make_result(score, f"{count} possible fragments (soft allowance {allowed:.1f})", "sentence_integrity")


def score_real_sources(text):
    """Check attribution signals only; this does not verify source truth."""
    count = 0
    for pattern in REAL_SOURCE_PATTERNS:
        count += len(re.findall(pattern, text))
    score = min(1.0, count / 5.0)
    return _make_result(score, f"{count} source-attribution signals (not fact verification)", "source_attribution")


def score_register_consistency(text):
    """Flag uncontrolled mixing of jargon, chatty fillers, and internet slang."""
    bands = [
        sum(text.count(w) for w in COLD_WORDS),
        sum(text.count(w) for w in WARM_WORDS),
        sum(text.count(w) for w in HOT_WORDS),
        sum(text.count(w) for w in WILD_WORDS),
    ]
    active = sum(1 for count in bands if count >= 3)
    score = 1.0 if active <= 2 else max(0.4, 1.0 - (active - 2) * 0.3)
    return _make_result(score, f"heavily used vocabulary bands={active}/4", "register_consistency")


def score_insertion_control(text):
    """Allow natural insertions but penalize repeated scripted self-correction."""
    count = 0
    for pattern in SELF_CORRECTION_PATTERNS:
        count += len(re.findall(pattern, text))
    score = 1.0 if count <= 3 else max(0.0, 1.0 - (count - 3) / 8)
    return _make_result(score, f"{count} self-corrections/insertions", "insertion_control")


# ============================================================
# Tier Runners
# ============================================================

TIER1_CHECKS = [
    ("sentence_length_stddev", score_sentence_length_stddev),
    ("sentence_length_range", score_sentence_length_range),
    ("paragraph_length_variance", score_paragraph_length_variance),
    ("vocabulary_richness", score_vocabulary_richness),
    ("emotional_balance", score_emotional_balance),
    ("adverb_density", score_adverb_density),
]

TIER2_CHECKS = [
    ("banned_words", score_banned_words),
    ("sentence_integrity", score_sentence_integrity),
    ("real_sources", score_real_sources),
    ("register_consistency", score_register_consistency),
    ("insertion_control", score_insertion_control),
]


def run_tier(checks, text):
    """Run a tier of checks. Returns dict keyed by check name + _summary."""
    results = {}
    scores = []
    for name, fn in checks:
        r = fn(text)
        results[name] = r
        scores.append(r["score"])
    results["_summary"] = {
        "count": len(checks),
        "mean_score": round(sum(scores) / len(scores), 4) if scores else 0,
        "scores": [round(s, 4) for s in scores],
    }
    return results


# ============================================================
# Calibration (bell-curve + over-optimization penalty)
# ============================================================

# Human article baselines (from 15 example articles, 2026-03-30)
# Dimensions where AI over-optimizes: bell-curve scoring penalizes
# both "too low" AND "too high" relative to human average.
_BELL_CURVE_CHECKS = {}


def _bell_curve(raw_score, center):
    """Score peaks at center (human avg), penalizes over-optimization.

    Below center: linear rise (as before).
    Above center: quadratic penalty — too much is suspicious.
    """
    if center <= 0:
        return raw_score
    if raw_score <= center:
        return raw_score / center
    else:
        overshoot = (raw_score - center) / (1.0 - center) if center < 1 else 0
        return max(0.0, 1.0 - overshoot * overshoot)


def calibrate_tiers(tier1, tier2):
    """Apply bell-curve calibration and over-optimization penalty in-place."""
    # 1. Bell-curve adjustment for over-optimizable dimensions
    for tier in [tier1, tier2]:
        for name, data in tier.items():
            if name.startswith("_"):
                continue
            if name in _BELL_CURVE_CHECKS:
                raw = data["score"]
                center = _BELL_CURVE_CHECKS[name]
                calibrated = round(max(0.0, min(1.0, _bell_curve(raw, center))), 4)
                data["raw_score"] = raw
                data["score"] = calibrated
                data["detail"] += f" [calibrated from {raw:.2f}, center={center}]"

    # Clear writing should not be penalized for scoring well.
    all_scores = []
    for tier in [tier1, tier2]:
        for name, data in tier.items():
            if not name.startswith("_"):
                all_scores.append(data["score"])

    penalty = 1.0

    if penalty < 1.0:
        for tier in [tier1, tier2]:
            for name, data in tier.items():
                if not name.startswith("_"):
                    data["score"] = round(data["score"] * penalty, 4)

    # 3. Recalculate tier summaries
    for tier in [tier1, tier2]:
        scores = [data["score"] for name, data in tier.items() if not name.startswith("_")]
        tier["_summary"]["mean_score"] = round(sum(scores) / len(scores), 4) if scores else 0
        tier["_summary"]["scores"] = [round(s, 4) for s in scores]

    return penalty


# ============================================================
# Composite Score
# ============================================================

def compute_composite(tier1, tier2, tier3_score=None):
    """Compute compatibility risk score (0=lower risk, 100=higher risk).

    With tier3: T1=50%, T2=30%, T3=20%
    Without:    T1=62.5%, T2=37.5%
    """
    t1_mean = tier1["_summary"]["mean_score"]
    t2_mean = tier2["_summary"]["mean_score"]

    if tier3_score is not None:
        quality = t1_mean * 0.50 + t2_mean * 0.30 + tier3_score * 0.20
        weights = {"tier1": 0.50, "tier2": 0.30, "tier3": 0.20}
    else:
        quality = t1_mean * 0.625 + t2_mean * 0.375
        weights = {"tier1": 0.625, "tier2": 0.375}

    composite = round((1 - quality) * 100, 2)
    return composite, weights


def build_param_scores(tier1, tier2):
    """Build flat param→score map for optimization. Averages if multiple checks map to same param."""
    param_map = {}
    for tier in [tier1, tier2]:
        for name, data in tier.items():
            if name.startswith("_"):
                continue
            param = data.get("param")
            if param is None:
                continue
            if param not in param_map:
                param_map[param] = []
            param_map[param].append(data["score"])
    return {p: round(sum(scores) / len(scores), 4) for p, scores in param_map.items()}


# ============================================================
# Main API
# ============================================================

def score_article(text, verbose=False, tier3_score=None):
    """Score an article. Returns full results dict."""
    clean = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE).strip()

    tier1 = run_tier(TIER1_CHECKS, clean)
    tier2 = run_tier(TIER2_CHECKS, clean)
    over_opt_penalty = calibrate_tiers(tier1, tier2)
    composite, weights = compute_composite(tier1, tier2, tier3_score)
    param_scores = build_param_scores(tier1, tier2)

    result = {
        # Canonical public score: higher is better. composite_score remains for
        # backward compatibility with history files created before v3.7.
        "quality_score": round(100 - composite, 2),
        "composite_score": composite,
        "tier1": tier1,
        "tier2": tier2,
        "tier3": {
            "score": tier3_score,
            "source": "agent" if tier3_score is not None else "not_available",
        },
        "weights": weights,
        "param_scores": param_scores,
        "over_optimization_penalty": over_opt_penalty,
        "char_count": len(clean),
    }

    if verbose:
        _print_verbose(result)

    return result


def _print_verbose(result):
    """Print a human-readable report."""
    quality = result["quality_score"]
    print(f"\n{'=' * 60}")
    print(f"WRITING QUALITY SCORE: {quality:.1f}/100 (higher = better)")
    print(f"{'=' * 60}")

    for tier_name, tier_label, weight in [
        ("tier1", "Tier 1 — Rhythm and readability", result["weights"].get("tier1", 0)),
        ("tier2", "Tier 2 — Language risks", result["weights"].get("tier2", 0)),
    ]:
        tier = result[tier_name]
        summary = tier["_summary"]
        print(f"\n{tier_label} (weight {weight:.0%}, mean {summary['mean_score']:.2f})")
        for name, data in tier.items():
            if name.startswith("_"):
                continue
            bar = "█" * int(data["score"] * 10) + "░" * (10 - int(data["score"] * 10))
            param_tag = f" [{data['param']}]" if data.get("param") else ""
            print(f"  {bar} {data['score']:.2f}  {name}{param_tag}")
            print(f"         {data['detail']}")

    t3 = result["tier3"]
    if t3["score"] is not None:
        t3_weight = result["weights"].get("tier3", 0)
        print(f"\nTier 3 — LLM (weight {t3_weight:.0%})")
        print(f"  Score: {t3['score']:.2f} (source: {t3['source']})")
    else:
        print(f"\nTier 3 — LLM: not available (standalone mode)")

    print(f"\nQuality: {quality:.1f} (100=better writing signals)")
    print(f"Weights: {result['weights']}")

    param_scores = result["param_scores"]
    if param_scores:
        sorted_params = sorted(param_scores.items(), key=lambda x: x[1])
        print(f"\nLowest-scoring parameters (optimize these first):")
        for param, score in sorted_params[:3]:
            print(f"  {param}: {score:.2f}")


# ============================================================
# Calibration Baselines
# ============================================================

CALIBRATION_BASELINES = {
    "needs_edit": {"label": "Needs editing", "expected_quality_min": 0, "expected_quality_max": 49},
    "review": {"label": "Review suggested", "expected_quality_min": 50, "expected_quality_max": 69},
    "clear": {"label": "Few mechanical risks", "expected_quality_min": 70, "expected_quality_max": 100},
}


def _calibration_verdict(result):
    """Return calibration info dict with target range and verdict."""
    quality = result["quality_score"]
    t_min, t_max = 70, 100
    verdict = "Few mechanical risks" if quality >= 70 else "Editorial review suggested"
    return {
        "target_min": t_min,
        "target_max": t_max,
        "verdict": verdict,
    }


def _print_calibration(result):
    """Print calibration comparison table."""
    quality = result["quality_score"]
    cal = _calibration_verdict(result)

    print(f"\n{'=' * 60}")
    print(f"CALIBRATION COMPARISON")
    print(f"{'=' * 60}")
    print(f"  Your article:  {quality:.1f}/100")
    print()
    for key, baseline in CALIBRATION_BASELINES.items():
        lo = baseline["expected_quality_min"]
        hi = baseline["expected_quality_max"]
        marker = ""
        if lo <= quality <= hi:
            marker = "  <-- YOUR SCORE IS HERE"
        print(f"  {baseline['label']:.<40s} {lo}-{hi}{marker}")
    print()
    print(f"  Verdict: {cal['verdict']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Score article writing quality (0-100, higher is better)")
    parser.add_argument("input", help="Markdown article file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed report")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--tier3", type=float, default=None,
                        help="Tier 3 LLM score (0-1), passed by agent from SKILL.md")
    parser.add_argument("--calibrate", action="store_true",
                        help="Show broad style-risk bands")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    result = score_article(text, verbose=args.verbose, tier3_score=args.tier3)

    if args.calibrate:
        _print_calibration(result)

    if args.json:
        if args.verbose or args.calibrate:
            result["calibration"] = _calibration_verdict(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not args.verbose and not args.calibrate:
        print(f"{result['quality_score']:.1f}")


if __name__ == "__main__":
    main()
