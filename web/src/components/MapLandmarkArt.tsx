import { useId, type CSSProperties } from "react";
import "./map-landmark-art.css";

const LIGHTS: Record<string, string> = {
  dust2: "#F59E0B", mirage: "#F43F5E", ancient: "#10B981", anubis: "#EAB308",
  inferno: "#F97316", nuke: "#06B6D4", cache: "#64748B",
};

/** Original architectural vignettes, kept beneath any owner-provided scenic photo. */
export default function MapLandmarkArt({ id }: { id: string }) {
  const map = id.replace(/^de_/, "").toLowerCase();
  const uid = `landmark-${useId().replace(/:/g, "")}`;
  if (!LIGHTS[map]) return null;

  return <svg className="map-landmark-art" data-landmark={map} viewBox="0 0 200 132" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false" style={{ "--landmark-light": LIGHTS[map] } as CSSProperties}>
    <defs>
      <linearGradient id={`${uid}-sky`} x1="0" y1="1" x2=".8" y2="0">
        <stop stopColor="var(--landmark-light)" stopOpacity=".06" />
        <stop offset="1" stopColor="var(--landmark-light)" stopOpacity=".32" />
      </linearGradient>
      <linearGradient id={`${uid}-ray`} x1="0" y1="1" x2="1" y2="0">
        <stop stopColor="var(--landmark-light)" stopOpacity="0" />
        <stop offset="1" stopColor="var(--landmark-light)" stopOpacity=".47" />
      </linearGradient>
      <linearGradient id={`${uid}-fade`} x2="0" y2="1">
        <stop offset=".65" stopColor="white" /><stop offset="1" stopColor="black" />
      </linearGradient>
      <mask id={`${uid}-mask`}><rect width="200" height="132" fill={`url(#${uid}-fade)`} /></mask>
    </defs>
    <g mask={`url(#${uid}-mask)`}>
      <rect width="200" height="132" fill={`url(#${uid}-sky)`} />
      <g className="landmark-distance">
        <path d="M0 100V74h22V62h15v17h18V65h27v22h23V72h24v9h20V61h25v15h26v56H0Z" />
        <path d="M0 111 32 102 57 106 87 97 120 104 159 94 200 106V132H0Z" />
      </g>
      <g fill={`url(#${uid}-ray)`}>
        <path d="M155-8 37 132H3L137-8Z" />
        <path d="M173-8 110 132H68L159-8Z" />
        <path d="M192-8 182 132H139L179-8Z" />
      </g>
      {map === "dust2" && <>
        <g className="landmark-rear">
          <path d="M22 95V61h5c0-16 12-24 24-29 12 5 24 13 24 29h5v34ZM98 99V38h9V25h4V12l3-5 3 5v13h4v13h8v61Z" />
          <path className="landmark-edge" d="M20 61h62M25 67h52M97 39h33M104 26h20M111 14h6" />
        </g>
        <path className="landmark-building" d="M26 132V96C26 50 70 45 85 77c15-32 59-27 59 19v36Z" />
        <path className="landmark-opening" d="M35 132V97c0-37 42-37 42 0v35Zm58 0V97c0-37 42-37 42 0v35Z" />
        <g className="landmark-detail"><path d="M39 97h34v35H39Zm58 0h34v35H97ZM48 98v34m16-34v34m42-34v34m16-34v34M39 108h34m-34 13h34m24-13h34m-34 13h34" /><path d="M57 95v37m58-37v37" /></g>
        <path className="landmark-edge" d="M27 97c0-43 44-47 58-17 14-30 58-26 58 17M23 132V98m125 34V98" />
      </>}
      {map === "mirage" && <>
        <g className="landmark-rear"><path d="M132 107V43h7V31h10V19l9-11 9 11v12h9v12h7v64Z" /><path className="landmark-edge" d="M133 45h50M140 31h35M143 55v12m10-12v12m11-12v12m10-12v12" /></g>
        <path className="landmark-building" d="M11 132V73h8V61h9v8h9v-8h9v8h9v-8h9v8h9v-8h9v8h9v-8h9v8h9v-8h9v12h9v59Z" />
        <path className="landmark-opening" d="M25 132V98c0-23 25-23 25 0v34Zm40 0V98c0-23 25-23 25 0v34Zm40 0V98c0-23 25-23 25 0v34Z" />
        <g className="landmark-edge"><path d="M16 78h120M21 83h111M21 132V98c0-28 33-28 33 0v34m7 0V98c0-28 33-28 33 0v34m7 0V98c0-28 33-28 33 0v34M54 113h7m33 0h7" /></g>
        <path className="landmark-detail" d="M148 100V80q9-13 18 0v20m-18-4h18m-18-7h18M17 120h8m25 0h15m25 0h15m25 0h12" />
      </>}
      {map === "ancient" && <>
        <path className="landmark-rear" d="M0 111V68l11-22 8 18 11-36 12 33 8-9 15 49h86l10-40 13 12 10-46 16 45v60H0Z" />
        <path className="landmark-building" d="M29 132v-15h14v-14h14V89h14V75h14V46h43v29h14v14h14v14h14v14h14v15Z" />
        <path className="landmark-edge" d="M27 117h159M42 103h130M55 89h103M69 75h75M82 46h49M80 42h53M91 34h31v8" />
        <path className="landmark-opening" d="M98 75V54h18v21Z" />
        <path className="landmark-detail" d="m96 132 6-57h9l6 57M98 85h15m-16 8h17m-18 8h19m-20 8h21m-22 9h23m-23 8h24M50 108h12m66-15h10m-62-9h9m40-25h4" />
        <g className="landmark-vines"><path d="M25 14q-10 29 2 45t-6 33M170 11q19 24 5 47t10 46M7 26q20 4 27-4m-9 27 12 8m139-19-13 6m11 19 13 6M54 1q-3 24-24 33" /><path d="m25 56-10 6 10 3m152-17 11-5-2 10m-143-36 9 5-10 5" /></g>
      </>}
      {map === "anubis" && <>
        <g className="landmark-rear"><path d="m142 112 3-75 9-22 9 22 3 75ZM20 119l2-54 6-15 6 15 2 54Z" /><path className="landmark-edge" d="m145 38 9-5 9 5m-9-20v94M22 67l6-4 6 4" /></g>
        <path className="landmark-building" d="M45 132v-13h12V83l12-16 2-30 8-27 9 35 10-23 4 34 21 10 17 3-3 12-25 4-8 13 11 21h15v13Z" />
        <path className="landmark-edge" d="m80 22 3 39-12 12m29-32-8 24 28 10 18-2M61 119h54M58 111h52M57 103h49" />
        <path className="landmark-detail" d="m79 85 12 4 14-5m-25 8 10 4 10-4m-34 27 10-22m25 22-7-21M88 72l10 1-5 4Z" />
        <path className="landmark-building" d="M5 132v-7h39v7m96 0v-10h48v10" />
      </>}
      {map === "inferno" && <>
        <g className="landmark-rear"><path d="M21 109V46h6V35h6V23L49 9l16 14v12h6v11h6v63Z" /><path className="landmark-edge" d="M27 46h44M31 35h36M32 24h34M26 76h47" /><path className="landmark-opening" d="M37 66V55q0-11 9-11t9 11v11ZM57 66V54q0-9 7-9v21Z" /><circle className="landmark-opening" cx="49" cy="29" r="6" /><path className="landmark-edge" d="M49 25v4l3 2" /></g>
        <path className="landmark-building" d="M4 132V95l20-6h151l25 7v36Z" />
        <path className="landmark-opening" d="M29 132v-16c0-27 35-27 35 0v16Zm51 0v-17c0-34 42-34 42 0v17Zm58 0v-16c0-27 35-27 35 0v16Z" />
        <path className="landmark-edge" d="m4 91 21-8h149l26 8M4 97h196M25 132v-16c0-33 43-33 43 0v16m8 0v-17c0-40 50-40 50 0v17m8 0v-16c0-33 43-33 43 0v16" />
        <path className="landmark-detail" d="M11 102h27m-15-5v5m43 5h18m40 0h18m21-5h28m-17-5v5m-47 13h8m-67 0h9m-66 1h12m151 0h12" />
      </>}
      {map === "nuke" && <>
        <path className="landmark-rear" d="M0 126V99h12V81h41v12h37V78h27v17h44V83h39v49H0Z" />
        <g className="landmark-building"><path d="M26 119c12-26 17-48 13-73h34c-4 25 1 47 13 73Zm58 5c15-33 19-59 14-87h39c-5 28-1 54 14 87Z" /></g>
        <g className="landmark-edge"><path d="M38 46q18 5 36 0M37 51q19 5 38 0M97 37q21 5 41 0M98 43q20 5 39 0M26 119h60m-2 5h67M45 57q3 34-10 56m27-56q-1 34 13 56m31-65q4 39-12 68m31-68q-3 39 15 68" /></g>
        <path className="landmark-pylon" d="m157 125 15-106 16 106m-34 0h38m-32-18h26m-23-20h20m-17-20h14m-11-21h8m-22-8h34m-38 19h42m-35 14 22 16-27 20 31 18m-31-18 27-20-22-16m3-25 8 21m-8 0 8-21M156 38 127 25M188 38l12-10M151 57l-13-4m55 4 7-3" />
        <path className="landmark-steam" d="M50 36c-13-11 11-16 0-30m63 21c-13-12 13-16 3-30" />
      </>}
      {map === "cache" && <>
        <g className="landmark-rear"><path d="M0 132V98h10V81h29v17h12V87h19v45Zm126 0V91h18V73h9v18h47v41Z" /></g>
        <g className="landmark-wheel"><circle cx="75" cy="60" r="39" /><circle cx="75" cy="60" r="34" /><circle cx="75" cy="60" r="5" /><path d="M75 21v78M36 60h78M47 32l56 56m0-56L47 88M60 24l30 72M39 45l72 30m-21-51L60 96m51-51L39 75M75 60l-23 69m23-69 23 69M47 129h56" /></g>
        <g className="landmark-building"><path d="M69 17h12v9H69Zm-33 9h11v10H36Zm-6 29h12v10H30Zm10 29h12v10H40Zm29 11h12v10H69Zm29-11h12v10H98Zm11-29h12v10h-12Zm-6-29h11v10h-11Z" /></g>
        <g className="landmark-pylon"><path d="M119 129V57h81m-81 13h81m-77-13 13 13 13-13 13 13 13-13 13 13 12-13m-81 23 16 16-16 16 16 17m-16-17 16-16-16-16m16-23v72m48-72v72m-10 0h20" /></g>
      </>}
      <path className="landmark-ground" d="M0 124 20 119 42 125 67 122 95 127 124 119 148 125 175 120 200 125v7H0Z" />
    </g>
  </svg>;
}
