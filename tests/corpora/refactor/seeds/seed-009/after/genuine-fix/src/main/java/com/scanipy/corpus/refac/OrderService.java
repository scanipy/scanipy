package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input008) throws Exception {
        String left008 = "SELECT * FROM orders WHERE id = '";
        String right008 = "'";
        String value008 = "SELECT * FROM orders WHERE id = ?";
        java.sql.PreparedStatement st = conn.prepareStatement(value008);
        st.setString(1, input008);
        st.executeQuery();
    }
}
