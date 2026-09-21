#!/usr/bin/env python3
"""
check_contrast.py - WCAG 2.2 AA contrast checker for DocuCluster design tokens.

Checks:
  - Text on background pairs: must be >= 4.5:1
  - Control borders on background: must be >= 3:1

Exit code 0 = all pass, 1 = at least one failure.
"""

import sys


def hex_to_rgb(hex_color):
    """Convert #RRGGBB to (R, G, B)."""
    h = hex_color.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def relative_luminance(hex_color):
    """Compute relative luminance per WCAG 2.2."""
    r, g, b = hex_to_rgb(hex_color)
    
    def linearize(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(fg, bg):
    """Compute WCAG contrast ratio between two hex colors."""
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# -- Design Tokens --

COLORS = {
    'bg-canvas':      '#0E1013',
    'bg-surface':     '#16191E',
    'bg-raised':      '#1E2228',
    'border-subtle':  '#2A2F37',
    'border-control': '#6E7888',
    'text-primary':   '#ECEEF1',
    'text-secondary': '#B4BAC4',
    'text-muted':     '#8E96A3',
    'text-disabled':  '#6B7280',
    'action-bg':      '#ECEEF1',
    'action-text':    '#0E1013',
    'error-text':     '#FFB4AB',
    'error-bg':       '#2A1517',
    'error-border':   '#A8484D',
    'success-text':   '#7EE0A8',
    'success-bg':     '#12261C',
    'success-border': '#307A50',
    'warn-text':      '#F2C46D',
    'warn-bg':        '#2B2212',
    'warn-border':    '#8A6E2E',
    'info-text':      '#93C5FD',
    'info-bg':        '#172135',
    'info-border':    '#406DA0',
}

# -- Text on Background Pairs (must be >= 4.5:1) --

TEXT_PAIRS = [
    ('text-primary',   'bg-canvas',  'Primary text on canvas'),
    ('text-primary',   'bg-surface', 'Primary text on surface'),
    ('text-primary',   'bg-raised',  'Primary text on raised'),
    ('text-secondary', 'bg-canvas',  'Secondary text on canvas'),
    ('text-secondary', 'bg-surface', 'Secondary text on surface'),
    ('text-secondary', 'bg-raised',  'Secondary text on raised'),
    ('text-muted',     'bg-canvas',  'Muted text on canvas'),
    ('text-muted',     'bg-surface', 'Muted text on surface'),
    ('text-muted',     'bg-raised',  'Muted text on raised'),
    ('action-text',    'action-bg',  'Action button text'),
    ('error-text',     'error-bg',   'Error text on error bg'),
    ('error-text',     'bg-surface', 'Error text on surface'),
    ('success-text',   'success-bg', 'Success text on success bg'),
    ('success-text',   'bg-surface', 'Success text on surface'),
    ('warn-text',      'warn-bg',    'Warning text on warn bg'),
    ('warn-text',      'bg-surface', 'Warning text on surface'),
    ('info-text',      'info-bg',    'Info text on info bg'),
    ('info-text',      'bg-surface', 'Info text on surface'),
]

# -- Control Borders on Background (must be >= 3:1) --

BORDER_PAIRS = [
    ('border-control', 'bg-canvas',  'Control border on canvas'),
    ('border-control', 'bg-surface', 'Control border on surface'),
    ('border-control', 'bg-raised',  'Control border on raised'),
    ('error-border',   'bg-surface', 'Error border on surface'),
    ('success-border', 'bg-surface', 'Success border on surface'),
    ('warn-border',    'bg-surface', 'Warning border on surface'),
    ('info-border',    'bg-surface', 'Info border on surface'),
]


def main():
    all_pass = True
    results = []

    for fg_key, bg_key, context in TEXT_PAIRS:
        fg = COLORS[fg_key]
        bg = COLORS[bg_key]
        ratio = contrast_ratio(fg, bg)
        passed = ratio >= 4.5
        if not passed:
            all_pass = False
        results.append((context, fg_key, bg_key, '%.2f:1' % ratio, '4.5:1', 'PASS' if passed else 'FAIL'))

    for fg_key, bg_key, context in BORDER_PAIRS:
        fg = COLORS[fg_key]
        bg = COLORS[bg_key]
        ratio = contrast_ratio(fg, bg)
        passed = ratio >= 3.0
        if not passed:
            all_pass = False
        results.append((context, fg_key, bg_key, '%.2f:1' % ratio, '3:1', 'PASS' if passed else 'FAIL'))

    # Print results table (ASCII only for Windows compatibility)
    print()
    header = '%-35s %-18s %-15s %-10s %-8s %s' % ('Context', 'FG', 'BG', 'Ratio', 'Min', 'Result')
    print(header)
    print('-' * 95)
    for context, fg_key, bg_key, ratio, minimum, result in results:
        marker = '[OK]' if result == 'PASS' else '[!!]'
        print('%-35s %-18s %-15s %-10s %-8s %s %s' % (context, fg_key, bg_key, ratio, minimum, marker, result))
    
    print()
    if all_pass:
        print('[OK] All %d checks passed (WCAG 2.2 AA)' % len(results))
    else:
        fail_count = sum(1 for r in results if r[-1] == 'FAIL')
        print('[!!] %d of %d checks FAILED' % (fail_count, len(results)))

    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
