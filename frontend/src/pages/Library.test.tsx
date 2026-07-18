import { render, screen } from '@testing-library/react';

import { renderSnippet } from './Library';

describe('renderSnippet', () => {
  it('renders match highlights without injecting HTML', () => {
    render(<p>{renderSnippet('the <mark>roof</mark> and <script>alert(1)</script>')}</p>);
    const mark = screen.getByText('roof');
    expect(mark.tagName).toBe('MARK');
    // The script tag must be rendered as inert text, not parsed as HTML.
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
  });
});
