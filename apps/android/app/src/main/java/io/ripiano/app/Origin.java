package io.ripiano.app;

import java.net.URI;

final class Origin {
    private Origin() {}

    static String serverOrigin(String value) {
        try {
            URI uri = new URI(value.trim());
            if (uri.getPath() != null && !uri.getPath().isEmpty() && !"/".equals(uri.getPath())) return null;
            if (uri.getQuery() != null || uri.getFragment() != null) return null;
            return originOfUrl(value);
        } catch (Exception ignored) { return null; }
    }

    static String originOfUrl(String value) {
        try {
            URI uri = new URI(value.trim());
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null) return null;
            int port = uri.getPort() == 443 ? -1 : uri.getPort();
            if (port < -1 || port > 65535) return null;
            return new URI("https", null, uri.getHost().toLowerCase(), port, null, null, null).toString();
        } catch (Exception ignored) { return null; }
    }
}
