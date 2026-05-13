"use client";

import { useRef, useMemo, useEffect, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

const PARTICLE_COUNT = 2400;
const STAGES = [
  { x: -3.2, label: "Data Ingestion" },
  { x: -0.8, label: "Risk Scoring" },
  { x: 1.6, label: "Decision" },
  { x: 3.6, label: "Compliance" },
];

// Colors: blue (low risk) → amber (medium) → green (approved) / red (rejected)
const COLOR_INGEST = new THREE.Color(0.18, 0.45, 0.95);
const COLOR_RISK_LOW = new THREE.Color(0.1, 0.78, 0.55);
const COLOR_RISK_MED = new THREE.Color(0.92, 0.7, 0.15);
const COLOR_RISK_HIGH = new THREE.Color(0.9, 0.2, 0.25);
const COLOR_APPROVED = new THREE.Color(0.05, 0.85, 0.5);
const COLOR_GLOW = new THREE.Color(0.3, 0.55, 1.0);

function ParticleSystem() {
  const meshRef = useRef<THREE.Points>(null);
  const { size } = useThree();

  const { positions, velocities, colors, phases, riskBands, sizes } = useMemo(() => {
    const pos = new Float32Array(PARTICLE_COUNT * 3);
    const vel = new Float32Array(PARTICLE_COUNT * 3);
    const col = new Float32Array(PARTICLE_COUNT * 3);
    const ph = new Float32Array(PARTICLE_COUNT);
    const rb = new Float32Array(PARTICLE_COUNT);
    const sz = new Float32Array(PARTICLE_COUNT);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      // Start spread across the pipeline
      pos[i * 3] = (Math.random() - 0.3) * 8 - 1.5;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 3.5;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 2.0;

      vel[i * 3] = 0.3 + Math.random() * 0.6;
      vel[i * 3 + 1] = (Math.random() - 0.5) * 0.15;
      vel[i * 3 + 2] = (Math.random() - 0.5) * 0.1;

      ph[i] = Math.random() * Math.PI * 2;
      rb[i] = Math.random(); // 0-0.6 = low, 0.6-0.85 = med, 0.85-1 = high
      sz[i] = 1.5 + Math.random() * 3.0;

      col[i * 3] = COLOR_INGEST.r;
      col[i * 3 + 1] = COLOR_INGEST.g;
      col[i * 3 + 2] = COLOR_INGEST.b;
    }
    return { positions: pos, velocities: vel, colors: col, phases: ph, riskBands: rb, sizes: sz };
  }, []);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
    return geo;
  }, [positions, colors, sizes]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const posAttr = geometry.attributes.position as THREE.BufferAttribute;
    const colAttr = geometry.attributes.color as THREE.BufferAttribute;
    const posArr = posAttr.array as Float32Array;
    const colArr = colAttr.array as Float32Array;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const idx = i * 3;
      const phase = phases[i];
      const risk = riskBands[i];

      // Move forward
      posArr[idx] += velocities[idx] * 0.012;
      posArr[idx + 1] += Math.sin(t * 1.2 + phase) * 0.003 + velocities[idx + 1] * 0.004;
      posArr[idx + 2] += Math.cos(t * 0.9 + phase) * 0.002;

      // Converge toward center Y as they approach decision stage
      const progress = (posArr[idx] + 3.5) / 7.5; // 0 to 1
      const convergeFactor = Math.max(0, progress - 0.3) * 0.008;
      posArr[idx + 1] *= (1 - convergeFactor);

      // Wrap around when past right edge
      if (posArr[idx] > 4.5) {
        posArr[idx] = -4.0 + Math.random() * 0.5;
        posArr[idx + 1] = (Math.random() - 0.5) * 3.5;
        posArr[idx + 2] = (Math.random() - 0.5) * 2.0;
      }

      // Color based on x-position (stage) and risk band
      const x = posArr[idx];
      let color: THREE.Color;
      if (x < -1.8) {
        color = COLOR_INGEST;
      } else if (x < 0.5) {
        // Risk scoring zone - color by risk
        if (risk < 0.6) color = COLOR_RISK_LOW;
        else if (risk < 0.85) color = COLOR_RISK_MED;
        else color = COLOR_RISK_HIGH;
      } else {
        // Decision/compliance zone
        if (risk < 0.85) color = COLOR_APPROVED;
        else color = COLOR_RISK_HIGH;
      }

      // Smooth color transition
      colArr[idx] += (color.r - colArr[idx]) * 0.04;
      colArr[idx + 1] += (color.g - colArr[idx + 1]) * 0.04;
      colArr[idx + 2] += (color.b - colArr[idx + 2]) * 0.04;
    }

    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
  });

  const material = useMemo(() => {
    return new THREE.ShaderMaterial({
      vertexShader: `
        attribute float size;
        attribute vec3 color;
        varying vec3 vColor;
        varying float vAlpha;
        void main() {
          vColor = color;
          vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * (280.0 / -mvPos.z);
          gl_Position = projectionMatrix * mvPos;
          vAlpha = smoothstep(4.5, 3.0, abs(position.x)) * 0.85;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        varying float vAlpha;
        void main() {
          vec2 center = gl_PointCoord - 0.5;
          float dist = length(center);
          if (dist > 0.5) discard;
          float alpha = smoothstep(0.5, 0.1, dist) * vAlpha;
          gl_FragColor = vec4(vColor, alpha);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  }, []);

  return <points ref={meshRef} geometry={geometry} material={material} />;
}

// Pipeline stage nodes (glowing orbs at each stage)
function StageNodes() {
  const groupRef = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    const t = clock.getElapsedTime();
    groupRef.current.children.forEach((child, i) => {
      const scale = 1 + Math.sin(t * 1.5 + i * 1.2) * 0.08;
      child.scale.setScalar(scale);
    });
  });

  return (
    <group ref={groupRef}>
      {STAGES.map((stage, i) => (
        <mesh key={i} position={[stage.x, 0, 0]}>
          <sphereGeometry args={[0.12, 24, 24]} />
          <meshBasicMaterial
            color={i < 2 ? COLOR_GLOW : COLOR_APPROVED}
            transparent
            opacity={0.6}
          />
        </mesh>
      ))}
    </group>
  );
}

// Connecting flow lines between stages
function FlowLines() {
  const ref = useRef<THREE.Group>(null);

  const lines = useMemo(() => {
    return STAGES.slice(0, -1).map((stage, i) => {
      const next = STAGES[i + 1];
      const points: THREE.Vector3[] = [];
      for (let t = 0; t <= 1; t += 0.05) {
        points.push(
          new THREE.Vector3(
            THREE.MathUtils.lerp(stage.x, next.x, t),
            Math.sin(t * Math.PI) * 0.15,
            0
          )
        );
      }
      const geo = new THREE.BufferGeometry().setFromPoints(points);
      const mat = new THREE.LineBasicMaterial({ color: COLOR_GLOW, transparent: true, opacity: 0.15 });
      return new THREE.Line(geo, mat);
    });
  }, []);

  return (
    <group ref={ref}>
      {lines.map((lineObj, i) => (
        <primitive key={i} object={lineObj} />
      ))}
    </group>
  );
}

function Scene() {
  return (
    <>
      <ParticleSystem />
      <StageNodes />
      <FlowLines />
    </>
  );
}

export function HeroParticleStream({ className }: { className?: string }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div className={className} style={{ background: "linear-gradient(135deg, #0a1628 0%, #0f2a5e 50%, #0a1628 100%)" }} />
    );
  }

  return (
    <div className={className} style={{ background: "#050d1a" }}>
      <Canvas
        camera={{ position: [0, 0, 5.5], fov: 55 }}
        dpr={[1, 1.5]}
        gl={{ alpha: false, antialias: false }}
        style={{ pointerEvents: "none" }}
      >
        <color attach="background" args={["#050d1a"]} />
        <fog attach="fog" args={["#050d1a", 4, 9]} />
        <Scene />
      </Canvas>
    </div>
  );
}
