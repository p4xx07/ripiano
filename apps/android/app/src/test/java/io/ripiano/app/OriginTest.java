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
}
