package io.ripiano.app;

import org.junit.Test;

import static org.junit.Assert.*;

public class OriginTest {
    @Test public void defaultHttpsPortMatchesWebviewOrigin() {
        assertEquals("https://nas.example", Origin.serverOrigin("https://nas.example:443/"));
        assertEquals("https://nas.example", Origin.originOfUrl("https://nas.example/library?tag=a"));
        assertEquals("https://nas.example", Origin.originOfUrl("https://nas.example:443/api/session"));
    }

    @Test public void nonDefaultPortRemainsDistinctAndUnsafeOriginsAreRejected() {
        assertEquals("https://nas.example:8443", Origin.serverOrigin("https://nas.example:8443"));
        assertNotEquals("https://nas.example:8443", Origin.originOfUrl("https://nas.example/api/session"));
        assertNull(Origin.serverOrigin("http://nas.example"));
        assertNull(Origin.serverOrigin("https://nas.example/other"));
        assertNull(Origin.serverOrigin("https://user@nas.example"));
    }

    @Test public void onlyTheServerAndTheConfiguredSignInPageStayInsideTheApp() {
        String server = "https://ripiano.example.com", signIn = "https://auth.example.com";
        assertTrue(Origin.allowedInApp("https://ripiano.example.com/library", server, null));
        assertTrue(Origin.allowedInApp("https://auth.example.com/?rd=https%3A%2F%2Fripiano.example.com%2F", server, signIn));
        assertFalse(Origin.allowedInApp("https://auth.example.com/", server, null));
        assertFalse(Origin.allowedInApp("http://auth.example.com/", server, signIn));
        assertFalse(Origin.allowedInApp("https://auth.example.com.evil.test/", server, signIn));
        assertFalse(Origin.allowedInApp("https://jellyfin.example.com/", server, signIn));
        assertFalse(Origin.allowedInApp("not a url", server, signIn));
    }
}
