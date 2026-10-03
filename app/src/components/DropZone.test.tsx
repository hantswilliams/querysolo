// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Real-data brief R4: an s3:// path turns the line into `tables discover`, offers the
// public-bucket switch, and says so when the core has no credentials.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DropZone, NO_CREDENTIALS } from './DropZone';

const none = { configured: false, source: 'none' as const, profile: null, region: 'us-east-1', endpoint: null };

describe('DropZone with an s3:// path', () => {
  it('shows the discover line, the switch, and the no-credentials line until the switch is ticked', () => {
    const onPaths = vi.fn();
    render(<DropZone native={false} over={false} aws={none} onPaths={onPaths} onChoose={() => {}} />);
    const path = screen.getByTestId('path');
    fireEvent.change(path, { target: { value: 's3://acme-exports/events/' } });
    expect(screen.getByTestId('command').textContent).toContain('querysolo tables discover s3://acme-exports/events/');
    expect(screen.getByTestId('no-credentials').textContent).toBe(NO_CREDENTIALS);
    fireEvent.click(screen.getByTestId('public-bucket').querySelector('input')!);
    expect(screen.queryByTestId('no-credentials')).toBeNull();
    expect(screen.getByTestId('command').textContent).toContain('querysolo tables discover --anonymous s3://acme-exports/events/');
    fireEvent.click(screen.getByTestId('preview-path'));
    expect(onPaths).toHaveBeenCalledWith(['s3://acme-exports/events/'], true);
  });

  it('keeps the import line and no switch for a local path, and says nothing with credentials', () => {
    render(<DropZone native={false} over={false} aws={{ ...none, configured: true, source: 'environment' }} onPaths={() => {}} onChoose={() => {}} />);
    fireEvent.change(screen.getByTestId('path'), { target: { value: '/data/orders.csv' } });
    expect(screen.getByTestId('command').textContent).toContain('querysolo import /data/orders.csv');
    expect(screen.queryByTestId('public-bucket')).toBeNull();
    fireEvent.change(screen.getByTestId('path'), { target: { value: 's3://acme-exports/events/' } });
    expect(screen.queryByTestId('no-credentials')).toBeNull();
  });
});
