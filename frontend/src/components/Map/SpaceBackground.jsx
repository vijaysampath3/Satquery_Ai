import React, { useEffect, useRef } from 'react';

export default function SpaceBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationFrameId;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Generate Stars
    const numStars = 320;
    const stars = [];
    for (let i = 0; i < numStars; i++) {
      stars.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        radius: Math.random() * 1.6 + 0.4,
        alpha: Math.random() * 0.8 + 0.2,
        twinkleSpeed: (Math.random() * 0.02 + 0.005) * (Math.random() < 0.5 ? 1 : -1),
        color:
          Math.random() > 0.7
            ? '#a5b4fc' // Blue/Indigo star
            : Math.random() > 0.5
            ? '#38bdf8' // Cyan star
            : Math.random() > 0.3
            ? '#fbcfe8' // Pink/Magenta star
            : '#ffffff', // Pure white star
        flare: Math.random() > 0.9, // Bright star with flare cross
      });
    }

    // Generate Nebulae / Galaxy Dust Nodes
    const nebulae = [
      { x: window.innerWidth * 0.15, y: window.innerHeight * 0.25, r: 450, color: 'rgba(99, 102, 241, 0.16)' },
      { x: window.innerWidth * 0.85, y: window.innerHeight * 0.3, r: 500, color: 'rgba(168, 85, 247, 0.14)' },
      { x: window.innerWidth * 0.7, y: window.innerHeight * 0.8, r: 550, color: 'rgba(56, 189, 248, 0.12)' },
      { x: window.innerWidth * 0.2, y: window.innerHeight * 0.75, r: 400, color: 'rgba(236, 72, 153, 0.10)' },
    ];

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Deep cosmic space base fill
      ctx.fillStyle = '#02040a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Render Nebulae / Cosmic Dust Glows
      nebulae.forEach((n) => {
        const gradient = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r);
        gradient.addColorStop(0, n.color);
        gradient.addColorStop(0.5, n.color.replace(/[\d\.]+\)$/, '0.04)'));
        gradient.addColorStop(1, 'transparent');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();
      });

      // Render Stars
      stars.forEach((star) => {
        star.alpha += star.twinkleSpeed;
        if (star.alpha > 0.95 || star.alpha < 0.15) {
          star.twinkleSpeed = -star.twinkleSpeed;
        }

        ctx.save();
        ctx.globalAlpha = star.alpha;
        ctx.fillStyle = star.color;
        ctx.shadowBlur = star.radius * 4;
        ctx.shadowColor = star.color;

        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fill();

        // 4-Point Starburst Flare for major bright stars
        if (star.flare) {
          ctx.strokeStyle = star.color;
          ctx.lineWidth = 0.6;
          const flareLen = star.radius * 5;

          ctx.beginPath();
          ctx.moveTo(star.x - flareLen, star.y);
          ctx.lineTo(star.x + flareLen, star.y);
          ctx.moveTo(star.x, star.y - flareLen);
          ctx.lineTo(star.x, star.y + flareLen);
          ctx.stroke();
        }

        ctx.restore();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return <canvas ref={canvasRef} className="space-galaxy-canvas" />;
}
