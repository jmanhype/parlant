import { describe, expect, it } from "vitest";
import { MatcherOptions, render } from "@testing-library/react";
import { Matcher } from "vite";
import Chat from "./chat";

describe('Chat Component', () => {
    let getByRole: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    
    beforeEach(() => {
        const utils = render(<Chat sessionId=""/>);
        getByRole = utils.getByRole as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    });

    it('component should be rendered', () => {
        const submitButton = getByRole('button');
        expect(submitButton).toBeInTheDocument();
    });
});