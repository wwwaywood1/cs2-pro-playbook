import type { ReactNode } from "react";
import { PageSurface } from "../components/Page";
import { t, useLang } from "../i18n";

// Mirrors docs/CREDITS.md; keep both in sync. Chinese first, then English, in both UI languages.
const LINKS = {
  hltv: "https://www.hltv.org/",
  dataset: "https://huggingface.co/datasets/cs2povarchive/cs2-demos",
  bo3: "https://bo3.gg/",
  awpy: "https://github.com/pnxenopoulos/awpy",
  awpyData: "https://github.com/pnxenopoulos/awpy-data",
};

function A({ href, children }: { href: string; children: ReactNode }) {
  return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
}

interface Section { title: string; items: ReactNode[] }

const ZH: Section[] = [
  { title: "比赛数据", items: [
    <>本站的统计数据来自职业 CS2 比赛的 GOTV 录像（demo）。这些录像由各赛事主办方录制，作者从 <A href={LINKS.hltv}>HLTV.org</A> 的比赛页面手动下载；另有部分比赛来自 Hugging Face 上的 <A href={LINKS.dataset}>cs2povarchive/cs2-demos</A> 数据集（Apache-2.0 许可）。</>,
    <>比赛的具体日期已与 HLTV 和 <A href={LINKS.bo3}>bo3.gg</A> 交叉核对。</>,
    <>本站不重新分发任何 demo 文件，只发布由录像计算得到的统计结果。</>,
  ] },
  { title: "解析与地图素材", items: [
    <>Demo 解析使用 <A href={LINKS.awpy}>awpy</A>（MIT 许可）；雷达图与坐标换算来自 <A href={LINKS.awpyData}>awpy-data</A>。</>,
    <>Counter-Strike 2 及其素材（包括地图、雷达图与游戏画面）© Valve Corporation。本站是非商业的爱好者分析项目，与 Valve、HLTV、bo3.gg、任何赛事主办方或战队均无关联，也未获得其认可。</>,
    <>战队名称与标志是其各自所有者的商标，仅用于标识战队。</>,
  ] },
  { title: "方法", items: [
    <>回合胜率模型与行为价值（WPA）参考 Szmida &amp; Toka（MIT Sloan 体育分析大会，2025）与 Xenopoulos 等人（2020，Valuing Player Actions in Counter-Strike: Global Offensive）；数据处理与可视化思路参考 Xenopoulos 等人的 ggViz（2022）与 ESTA（2022）。AI 实验室页面另列出其所用文献。</>,
  ] },
  { title: "代码", items: [<>本站代码以 MIT 许可发布。</>] },
];

const EN: Section[] = [
  { title: "Match data", items: [
    <>Statistics on this site are derived from GOTV recordings (demos) of professional CS2 matches. The recordings are made by the tournament organisers; the author downloaded them by hand from <A href={LINKS.hltv}>HLTV.org</A> match pages, and some matches come from the <A href={LINKS.dataset}>cs2povarchive/cs2-demos</A> dataset on Hugging Face (Apache-2.0).</>,
    <>Exact match dates are cross-checked with HLTV and <A href={LINKS.bo3}>bo3.gg</A>.</>,
    <>Demo files are not redistributed; only statistics computed from them are published.</>,
  ] },
  { title: "Parsing and map assets", items: [
    <>Demos are parsed with <A href={LINKS.awpy}>awpy</A> (MIT). Radar images and coordinate transforms come from <A href={LINKS.awpyData}>awpy-data</A>.</>,
    <>Counter-Strike 2 and its assets (including maps, radar images and game imagery) © Valve Corporation. This is a non-commercial fan analysis project, not affiliated with or endorsed by Valve, HLTV, bo3.gg, any tournament organiser or team.</>,
    <>Team names and logos are trademarks of their respective owners, used only to identify the teams.</>,
  ] },
  { title: "Methods", items: [
    <>The round win-probability model and action values (WPA) draw on Szmida &amp; Toka (MIT Sloan Sports Analytics Conference, 2025) and Xenopoulos et al. (2020, Valuing Player Actions in Counter-Strike: Global Offensive); data processing and visualisation draw on Xenopoulos et al.'s ggViz (2022) and ESTA (2022). The AI Lab page lists the further works it uses.</>,
  ] },
  { title: "Code", items: [<>The site's code is released under the MIT licence.</>] },
];

function Block({ lang, heading, sections }: { lang: "zh" | "en"; heading: string; sections: Section[] }) {
  return <section className="about-block" lang={lang === "zh" ? "zh-CN" : "en"} aria-labelledby={`about-${lang}`}>
    <h2 id={`about-${lang}`}>{heading}</h2>
    {sections.map((section) => <div className="about-section" key={section.title}>
      <h3>{section.title}</h3>
      <ul>{section.items.map((item, index) => <li key={index}>{item}</li>)}</ul>
    </div>)}
  </section>;
}

export default function About() {
  useLang();
  return <PageSurface className="about-page">
    <header className="page-head"><div><p className="eyebrow">CS2 Pro Playbook</p><h1>{t("about.title")}</h1></div></header>
    <Block lang="zh" heading="中文" sections={ZH} />
    <Block lang="en" heading="English" sections={EN} />
  </PageSurface>;
}
