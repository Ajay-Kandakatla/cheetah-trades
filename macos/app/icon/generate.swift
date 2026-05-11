// generate.swift — produce Pounce's app icon at every size the macOS .icns
// format expects.
//
// Theme: intense desire. A locked-on predator eye — vertical-slit cat
// pupil inside a hot iris (red/orange gradient), set on a dark crimson
// radial background. Distilled symbol of focus, hunger, the moment before
// the pounce.
//
// Renders each size DIRECTLY at native pixel resolution (rather than
// downscaling from one master) so small sizes — especially 16/32 — stay
// crisp.
//
// Usage: invoked by build.sh; not meant to be run alone.

import Cocoa
import Foundation

// ---------------------------------------------------------------------------
// Output spec — the 10 PNG slots that .iconset / iconutil expects.
// ---------------------------------------------------------------------------
let renders: [(pixels: Int, name: String)] = [
    (16,   "icon_16x16.png"),
    (32,   "icon_16x16@2x.png"),
    (32,   "icon_32x32.png"),
    (64,   "icon_32x32@2x.png"),
    (128,  "icon_128x128.png"),
    (256,  "icon_128x128@2x.png"),
    (256,  "icon_256x256.png"),
    (512,  "icon_256x256@2x.png"),
    (512,  "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]

let outDir = URL(fileURLWithPath: "AppIcon.iconset")
try? FileManager.default.removeItem(at: outDir)
try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

for (px, name) in renders {
    let rep = renderIcon(pixels: px)
    try savePNG(rep: rep, to: outDir.appendingPathComponent(name))
    FileHandle.standardError.write("rendered \(name) (\(px)x\(px))\n".data(using: .utf8)!)
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------
func renderIcon(pixels: Int) -> NSBitmapImageRep {
    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: pixels, pixelsHigh: pixels,
        bitsPerSample: 8, samplesPerPixel: 4,
        hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0, bitsPerPixel: 32
    ) else {
        fatalError("failed to allocate bitmap rep")
    }
    rep.size = NSSize(width: pixels, height: pixels)

    NSGraphicsContext.saveGraphicsState()
    let nsCtx = NSGraphicsContext(bitmapImageRep: rep)!
    NSGraphicsContext.current = nsCtx
    let cg = nsCtx.cgContext
    let cs = CGColorSpaceCreateDeviceRGB()

    let w = CGFloat(pixels)
    let h = CGFloat(pixels)

    // -- Layer 1: background, full-bleed (macOS applies the squircle mask).
    //    Radial gradient: hot crimson core, fading to near-black, off-center
    //    upward to suggest a light source / ambient heat.
    let bg = CGGradient(
        colorsSpace: cs,
        colors: [
            CGColor(srgbRed: 0.78, green: 0.10, blue: 0.10, alpha: 1.0),  // crimson core
            CGColor(srgbRed: 0.32, green: 0.04, blue: 0.04, alpha: 1.0),  // mid red
            CGColor(srgbRed: 0.08, green: 0.02, blue: 0.02, alpha: 1.0),  // near black
        ] as CFArray,
        locations: [0.0, 0.55, 1.0]
    )!
    cg.drawRadialGradient(
        bg,
        startCenter: CGPoint(x: w * 0.50, y: h * 0.62), startRadius: 0,
        endCenter:   CGPoint(x: w * 0.50, y: h * 0.50), endRadius: w * 0.78,
        options: [.drawsAfterEndLocation]
    )

    // -- Layer 2: subtle vignette to deepen the corners.
    cg.saveGState()
    let vignette = CGGradient(
        colorsSpace: cs,
        colors: [
            CGColor(srgbRed: 0, green: 0, blue: 0, alpha: 0.0),
            CGColor(srgbRed: 0, green: 0, blue: 0, alpha: 0.55),
        ] as CFArray,
        locations: [0.55, 1.0]
    )!
    cg.drawRadialGradient(
        vignette,
        startCenter: CGPoint(x: w/2, y: h/2), startRadius: 0,
        endCenter:   CGPoint(x: w/2, y: h/2), endRadius: w * 0.72,
        options: [.drawsAfterEndLocation]
    )
    cg.restoreGState()

    // -- Layer 3: the eye. Almond shape with pointed corners — heavier
    //    upper lid to suggest a narrowed, predatory gaze.
    let eyeWidth  = w * 0.80
    let eyeHeight = h * 0.36
    let eyeRect = CGRect(
        x: (w - eyeWidth) / 2,
        y: (h - eyeHeight) / 2,
        width: eyeWidth, height: eyeHeight
    )
    let eyePath = predatorAlmondPath(in: eyeRect)

    // Soft outer glow under the eye — implies the iris is emitting heat.
    cg.saveGState()
    cg.setShadow(
        offset: .zero,
        blur: w * 0.06,
        color: CGColor(srgbRed: 1.0, green: 0.40, blue: 0.10, alpha: 0.45)
    )
    cg.addPath(eyePath)
    cg.setFillColor(CGColor(srgbRed: 1.0, green: 0.40, blue: 0.10, alpha: 1.0))
    cg.fillPath()
    cg.restoreGState()

    // Iris fill — radial hot-orange → deep red.
    cg.saveGState()
    cg.addPath(eyePath)
    cg.clip()
    let irisGrad = CGGradient(
        colorsSpace: cs,
        colors: [
            CGColor(srgbRed: 1.0,  green: 0.78, blue: 0.10, alpha: 1.0),  // gold core
            CGColor(srgbRed: 1.0,  green: 0.45, blue: 0.05, alpha: 1.0),  // hot orange
            CGColor(srgbRed: 0.80, green: 0.10, blue: 0.05, alpha: 1.0),  // deep red
            CGColor(srgbRed: 0.40, green: 0.03, blue: 0.02, alpha: 1.0),  // crimson rim
        ] as CFArray,
        locations: [0.0, 0.30, 0.75, 1.0]
    )!
    cg.drawRadialGradient(
        irisGrad,
        startCenter: CGPoint(x: w/2, y: h/2 + h * 0.02), startRadius: 0,
        endCenter:   CGPoint(x: w/2, y: h/2),             endRadius: eyeWidth / 1.9,
        options: [.drawsAfterEndLocation]
    )
    cg.restoreGState()

    // Eye outline — sharp dark rim defines the almond shape.
    cg.addPath(eyePath)
    cg.setStrokeColor(CGColor(srgbRed: 0.06, green: 0.0, blue: 0.0, alpha: 1.0))
    cg.setLineWidth(max(1.0, w * 0.014))
    cg.setLineJoin(.round)
    cg.strokePath()

    // -- Layer 4: vertical slit pupil. The single most expressive shape.
    //    Slightly tapered (lens-shaped) for menace.
    let pupilWidth  = max(1.5, w * 0.110)
    let pupilHeight = h * 0.32
    let pupilRect = CGRect(
        x: (w - pupilWidth) / 2,
        y: (h - pupilHeight) / 2,
        width: pupilWidth, height: pupilHeight
    )
    let pupil = pointedPupilPath(in: pupilRect)
    cg.addPath(pupil)
    cg.setFillColor(CGColor.black)
    cg.fillPath()

    // -- Layer 5: catchlight. Tiny offset highlight near the top of the
    //    pupil — implies a strong overhead light source on the iris.
    if pixels >= 32 {
        let cl = max(2.0, w * 0.038)
        let clRect = CGRect(
            x: w/2 - cl * 0.5 + w * 0.012,
            y: h/2 + pupilHeight * 0.32,
            width: cl, height: cl * 0.6
        )
        cg.setFillColor(CGColor(srgbRed: 1, green: 1, blue: 1, alpha: 0.92))
        cg.fillEllipse(in: clRect)
    }

    NSGraphicsContext.restoreGraphicsState()
    return rep
}

/// Almond eye outline, dramatically asymmetric — heavy hooded upper lid,
/// shallow lower lid. Reads as a narrowed, predatory glare.
func predatorAlmondPath(in rect: CGRect) -> CGPath {
    let cx = rect.midX, cy = rect.midY
    let halfW = rect.width / 2, halfH = rect.height / 2
    let p = CGMutablePath()
    p.move(to: CGPoint(x: cx - halfW, y: cy))
    // Top arc: heavy hooded curve, controls pulled outward and up.
    p.addCurve(
        to: CGPoint(x: cx + halfW, y: cy),
        control1: CGPoint(x: cx - halfW * 0.30, y: cy + halfH * 1.55),
        control2: CGPoint(x: cx + halfW * 0.30, y: cy + halfH * 1.55)
    )
    // Bottom arc: shallow, almost flat with a gentle dip.
    p.addCurve(
        to: CGPoint(x: cx - halfW, y: cy),
        control1: CGPoint(x: cx + halfW * 0.55, y: cy - halfH * 0.65),
        control2: CGPoint(x: cx - halfW * 0.55, y: cy - halfH * 0.65)
    )
    p.closeSubpath()
    return p
}

/// Lens-shaped pupil: tall, narrow, pointed at top and bottom.
func pointedPupilPath(in rect: CGRect) -> CGPath {
    let cx = rect.midX, cy = rect.midY
    let halfW = rect.width / 2, halfH = rect.height / 2
    let p = CGMutablePath()
    p.move(to: CGPoint(x: cx, y: cy + halfH))
    p.addCurve(
        to: CGPoint(x: cx, y: cy - halfH),
        control1: CGPoint(x: cx + halfW * 1.4, y: cy + halfH * 0.4),
        control2: CGPoint(x: cx + halfW * 1.4, y: cy - halfH * 0.4)
    )
    p.addCurve(
        to: CGPoint(x: cx, y: cy + halfH),
        control1: CGPoint(x: cx - halfW * 1.4, y: cy - halfH * 0.4),
        control2: CGPoint(x: cx - halfW * 1.4, y: cy + halfH * 0.4)
    )
    p.closeSubpath()
    return p
}

// ---------------------------------------------------------------------------
// PNG output
// ---------------------------------------------------------------------------
func savePNG(rep: NSBitmapImageRep, to url: URL) throws {
    guard let data = rep.representation(using: .png, properties: [:]) else {
        throw NSError(domain: "Pounce.icon", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "PNG encode failed"])
    }
    try data.write(to: url)
}
