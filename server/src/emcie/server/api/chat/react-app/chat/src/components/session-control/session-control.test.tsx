import { describe, expect, it, vi } from "vitest";
import SessionControl from "./session-control";
import { MatcherOptions, render } from "@testing-library/react";
import { Matcher } from "vite";

describe('Session Control Component', () => {
    let getByRole: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    
    beforeEach(() => {
        const utils = render(<SessionControl sessionId={null} setSession={vi.fn()}/>);
        getByRole = utils.getByRole as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    });

    it('component should be rendered', () => {
        const addButton = getByRole('button');
        expect(addButton).toBeInTheDocument();
    });
});