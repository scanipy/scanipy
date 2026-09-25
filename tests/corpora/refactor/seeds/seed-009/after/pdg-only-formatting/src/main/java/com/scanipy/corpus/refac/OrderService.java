// formatting only

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

        String value008 = left008 + input008 + right008;

        Statement st = conn.createStatement();

        st.executeQuery(value008);

    }

}
